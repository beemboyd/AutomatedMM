#!/usr/bin/env python3
"""
Hourly Strategy Predictor Service
Runs every hour during market hours to predict optimal strategy
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import joblib
import pytz
from typing import Dict, Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HourlyStrategyPredictor:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.models_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'models')
        self.breadth_data_dir = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 'historical_breadth_data')
        self.predictions_dir = os.path.join(self.base_dir, 'Daily', 'ML', 'predictions')
        self.results_dir = os.path.join(self.base_dir, 'Daily', 'results')
        self.results_s_dir = os.path.join(self.base_dir, 'Daily', 'results-s')
        
        # Create predictions directory
        os.makedirs(self.predictions_dir, exist_ok=True)
        
        # Timezone
        self.ist = pytz.timezone('Asia/Kolkata')
        
        # Load model
        self.model = None
        self.metadata = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained model"""
        try:
            model_path = os.path.join(self.models_dir, 'current_strategy_predictor.pkl')
            metadata_path = os.path.join(self.models_dir, 'current_strategy_metadata.json')
            
            if os.path.exists(model_path) and os.path.exists(metadata_path):
                self.model = joblib.load(model_path)
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
                logger.info("Model loaded successfully")
            else:
                logger.warning("No trained model found. Please train the model first.")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
    
    def get_current_features(self) -> Dict:
        """Get current feature values for prediction"""
        try:
            # Load latest breadth data
            breadth_file = os.path.join(self.breadth_data_dir, 'sma_breadth_historical_latest.json')
            with open(breadth_file, 'r') as f:
                breadth_data = json.load(f)
            
            # Convert to DataFrame
            df = pd.DataFrame(breadth_data)
            df['date'] = pd.to_datetime(df['date'])
            df['sma20_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma20_percent', 0))
            df['sma50_percent'] = df['sma_breadth'].apply(lambda x: x.get('sma50_percent', 0))
            
            # Sort by date
            df = df.sort_values('date')
            
            # Calculate features
            df['sma20_roc_1d'] = df['sma20_percent'].diff(1)
            df['sma20_roc_5d'] = df['sma20_percent'].diff(5)
            df['sma20_ma5'] = df['sma20_percent'].rolling(5).mean()
            df['sma20_ma10'] = df['sma20_percent'].rolling(10).mean()
            df['breadth_momentum'] = df['sma20_percent'] - df['sma20_ma5']
            
            # Get latest values
            latest = df.iloc[-1]
            
            # Count today's signals
            today = datetime.now(self.ist).date()
            long_count = self._count_signals(self.results_dir, today)
            short_count = self._count_signals(self.results_s_dir, today)
            
            # Calculate win rates (use last 5 days average)
            long_win_rate = 0.55  # Default
            short_win_rate = 0.45  # Default
            
            # Prepare features dictionary
            features = {
                'sma20_percent': latest['sma20_percent'],
                'sma50_percent': latest['sma50_percent'],
                'sma20_roc_1d': latest['sma20_roc_1d'],
                'sma20_roc_5d': latest['sma20_roc_5d'],
                'sma20_ma5': latest['sma20_ma5'],
                'sma20_ma10': latest['sma20_ma10'],
                'breadth_momentum': latest['breadth_momentum'],
                'long_signal_count': long_count,
                'short_signal_count': short_count,
                'signal_strength_diff': long_count - short_count,
                'long_win_rate': long_win_rate,
                'short_win_rate': short_win_rate
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error getting current features: {e}")
            return None
    
    def _count_signals(self, directory: str, date: datetime.date) -> int:
        """Count signals for a specific date"""
        count = 0
        date_str = date.strftime('%Y%m%d')
        
        try:
            files = os.listdir(directory)
            for file in files:
                if date_str in file and 'Reversal' in file:
                    try:
                        df = pd.read_excel(os.path.join(directory, file))
                        count += len(df)
                    except:
                        pass
        except Exception as e:
            logger.debug(f"Error counting signals: {e}")
        
        return count
    
    def make_prediction(self) -> Dict:
        """Make a prediction for current market conditions"""
        if self.model is None:
            return {
                'error': 'Model not loaded',
                'timestamp': datetime.now(self.ist).isoformat()
            }
        
        # Get current features
        features = self.get_current_features()
        if features is None:
            return {
                'error': 'Could not get current features',
                'timestamp': datetime.now(self.ist).isoformat()
            }
        
        # Prepare features for model
        feature_columns = self.metadata['feature_columns']
        X = pd.DataFrame([features])[feature_columns]
        
        # Make prediction
        prediction = self.model.predict(X)[0]
        prediction_proba = self.model.predict_proba(X)[0]
        
        # Get class probabilities
        classes = self.model.classes_
        proba_dict = {cls: float(prob) for cls, prob in zip(classes, prediction_proba)}
        
        # Calculate confidence
        confidence = float(max(prediction_proba))
        
        # Prepare response
        result = {
            'timestamp': datetime.now(self.ist).isoformat(),
            'prediction': {
                'recommended_strategy': prediction,
                'confidence': confidence,
                'probabilities': proba_dict
            },
            'current_conditions': {
                'sma20_breadth': features['sma20_percent'],
                'sma50_breadth': features['sma50_percent'],
                'breadth_momentum': features['breadth_momentum'],
                'long_signals_today': features['long_signal_count'],
                'short_signals_today': features['short_signal_count']
            },
            'insights': self._generate_insights(prediction, features, confidence)
        }
        
        return result
    
    def _generate_insights(self, prediction: str, features: Dict, confidence: float) -> Dict:
        """Generate actionable insights based on prediction"""
        insights = {
            'action_items': [],
            'risk_level': 'MEDIUM',
            'position_sizing': 'NORMAL'
        }
        
        # Strategy-specific recommendations
        if prediction == 'LONG':
            insights['action_items'].append("Focus on long reversal patterns")
            insights['action_items'].append("Monitor for pullbacks in strong stocks")
            
            if features['sma20_percent'] > 70:
                insights['risk_level'] = 'HIGH'
                insights['position_sizing'] = 'REDUCED'
                insights['action_items'].append("Market may be overbought - use tight stops")
            elif 55 <= features['sma20_percent'] <= 70:
                insights['risk_level'] = 'LOW'
                insights['position_sizing'] = 'NORMAL'
                insights['action_items'].append("Optimal conditions for long positions")
                
        elif prediction == 'SHORT':
            insights['action_items'].append("Focus on short reversal patterns")
            insights['action_items'].append("Look for weakness in overextended stocks")
            
            if features['sma20_percent'] < 30:
                insights['risk_level'] = 'HIGH'
                insights['position_sizing'] = 'REDUCED'
                insights['action_items'].append("Market may be oversold - quick profits recommended")
            elif 35 <= features['sma20_percent'] <= 50:
                insights['risk_level'] = 'LOW'
                insights['position_sizing'] = 'NORMAL'
                insights['action_items'].append("Good conditions for short positions")
                
        else:  # NEUTRAL
            insights['action_items'].append("Market conditions unclear - reduce position sizes")
            insights['action_items'].append("Wait for clearer signals")
            insights['risk_level'] = 'MEDIUM-HIGH'
            insights['position_sizing'] = 'REDUCED'
        
        # Confidence-based adjustments
        if confidence < 0.6:
            insights['action_items'].append("Low confidence - consider smaller positions")
            insights['position_sizing'] = 'REDUCED'
        
        # Breadth momentum insights
        if abs(features['breadth_momentum']) > 5:
            direction = 'improving' if features['breadth_momentum'] > 0 else 'deteriorating'
            insights['action_items'].append(f"Market breadth {direction} rapidly - monitor for regime change")
        
        return insights
    
    def save_prediction(self, prediction: Dict):
        """Save prediction for historical tracking"""
        try:
            # Daily predictions file
            date_str = datetime.now(self.ist).strftime('%Y%m%d')
            predictions_file = os.path.join(self.predictions_dir, f'predictions_{date_str}.json')
            
            # Load existing predictions
            if os.path.exists(predictions_file):
                with open(predictions_file, 'r') as f:
                    predictions = json.load(f)
            else:
                predictions = []
            
            # Add new prediction
            predictions.append(prediction)
            
            # Save
            with open(predictions_file, 'w') as f:
                json.dump(predictions, f, indent=2)
            
            # Also save as latest
            latest_file = os.path.join(self.predictions_dir, 'latest_prediction.json')
            with open(latest_file, 'w') as f:
                json.dump(prediction, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving prediction: {e}")
    
    def get_latest_prediction(self) -> Optional[Dict]:
        """Get the most recent prediction"""
        try:
            latest_file = os.path.join(self.predictions_dir, 'latest_prediction.json')
            if os.path.exists(latest_file):
                with open(latest_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading latest prediction: {e}")
        return None
    
    def run_prediction_cycle(self):
        """Run a complete prediction cycle"""
        logger.info("="*60)
        logger.info("Running Hourly Strategy Prediction")
        logger.info(f"Time: {datetime.now(self.ist).strftime('%Y-%m-%d %H:%M:%S IST')}")
        logger.info("="*60)
        
        # Check if market hours
        now = datetime.now(self.ist)
        if now.weekday() > 4:  # Weekend
            logger.info("Weekend - using last prediction")
            last_pred = self.get_latest_prediction()
            if last_pred:
                logger.info(f"Last prediction: {last_pred['prediction']['recommended_strategy']}")
            return
        
        hour = now.hour
        minute = now.minute
        
        if not (9 <= hour <= 15 or (hour == 15 and minute <= 30)):
            logger.info("Outside market hours - using last prediction")
            last_pred = self.get_latest_prediction()
            if last_pred:
                logger.info(f"Last prediction: {last_pred['prediction']['recommended_strategy']}")
            return
        
        # Make new prediction
        prediction = self.make_prediction()
        
        if 'error' not in prediction:
            # Save prediction
            self.save_prediction(prediction)
            
            # Log results
            logger.info(f"\nRecommended Strategy: {prediction['prediction']['recommended_strategy']}")
            logger.info(f"Confidence: {prediction['prediction']['confidence']:.2%}")
            logger.info(f"\nCurrent Conditions:")
            logger.info(f"  SMA20 Breadth: {prediction['current_conditions']['sma20_breadth']:.1f}%")
            logger.info(f"  Long Signals: {prediction['current_conditions']['long_signals_today']}")
            logger.info(f"  Short Signals: {prediction['current_conditions']['short_signals_today']}")
            
            logger.info(f"\nInsights:")
            for item in prediction['insights']['action_items']:
                logger.info(f"  - {item}")
            logger.info(f"  Risk Level: {prediction['insights']['risk_level']}")
            logger.info(f"  Position Sizing: {prediction['insights']['position_sizing']}")
        else:
            logger.error(f"Prediction error: {prediction['error']}")

def main():
    """Main function"""
    predictor = HourlyStrategyPredictor()
    predictor.run_prediction_cycle()

if __name__ == "__main__":
    main()