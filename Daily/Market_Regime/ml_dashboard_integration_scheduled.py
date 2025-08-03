#!/usr/bin/env python3
"""
ML Dashboard Integration with Scheduled Data Management
Handles weekday/weekend data logic for ML predictions
"""

import os
import sys
import json
import shutil
from datetime import datetime, timedelta
import pytz
from typing import Dict, Optional
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the original ML integration
from ml_dashboard_integration import MLDashboardIntegration

class ScheduledBreadthStrategyPredictor:
    """Wrapper for BreadthStrategyPredictor that handles scheduled data"""
    
    def __init__(self, base_predictor):
        self.base_predictor = base_predictor
        self.ist = pytz.timezone('Asia/Kolkata')
        
    def get_current_breadth_features(self) -> dict:
        """Get breadth features with scheduled data awareness"""
        # Temporarily override the data file path
        original_method = self.base_predictor.get_current_breadth_features
        
        # Get the appropriate data source
        integration = ScheduledMLDashboardIntegration()
        data_source = integration.get_data_source()
        
        # If using Friday cache, handle the wrapped data format
        if 'friday_cache' in data_source:
            try:
                with open(data_source, 'r') as f:
                    cache_data = json.load(f)
                
                # Extract actual data from cache
                if isinstance(cache_data, dict) and 'data' in cache_data:
                    breadth_data = cache_data['data']
                else:
                    breadth_data = cache_data
                
                # Temporarily save to latest file for processing
                temp_file = data_source.replace('friday_cache', 'temp_processing')
                with open(temp_file, 'w') as f:
                    json.dump(breadth_data, f)
                
                # Call original method with temp file
                result = original_method()
                
                # Clean up temp file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
                return result
                
            except Exception as e:
                logging.error(f"Error processing Friday cache: {e}")
                return original_method()
        else:
            return original_method()
    
    def get_strategy_recommendation(self) -> dict:
        """Get strategy recommendation with data source metadata"""
        features = self.get_current_breadth_features()
        
        if not features:
            return self.base_predictor.get_strategy_recommendation()
        
        # Get base recommendation
        rec = self.base_predictor.model.predict_optimal_strategy(features)
        
        # Add features and metadata
        integration = ScheduledMLDashboardIntegration()
        data_source = integration.get_data_source()
        is_cached = 'friday_cache' in data_source
        
        rec['current_features'] = {
            'sma20_breadth': features['sma20_percent'],
            'sma50_breadth': features['sma50_percent'],
            'breadth_momentum_1d': features['sma20_roc_1d'],
            'breadth_momentum_5d': features['sma20_roc_5d'],
            'breadth_trend': 'Uptrend' if features['uptrend'] else ('Downtrend' if features['downtrend'] else 'Neutral')
        }
        
        rec['rule_based'] = {
            'long_favorable': 55 <= features['sma20_percent'] <= 70,
            'short_favorable': 35 <= features['sma20_percent'] <= 50,
            'avoid_trading': features['sma20_percent'] < 20 or features['sma20_percent'] > 80
        }
        
        rec['data_source'] = 'friday_cache' if is_cached else 'live_data'
        
        return rec

class ScheduledMLDashboardIntegration(MLDashboardIntegration):
    """Extended ML Dashboard Integration with scheduled data management"""
    
    def __init__(self):
        """Initialize with scheduled data awareness"""
        super().__init__()
        self.ist = pytz.timezone('Asia/Kolkata')
        self.friday_data_path = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                            'historical_breadth_data', 'sma_breadth_friday_cache.json')
        
        # Wrap the predictor with scheduled version
        self.predictor = ScheduledBreadthStrategyPredictor(self.predictor)
        
    def is_market_hours(self) -> bool:
        """Check if current time is within market hours (Mon-Fri 9:15 AM - 3:30 PM IST)"""
        now = datetime.now(self.ist)
        
        # Check if weekday (0 = Monday, 4 = Friday)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
            
        # Check time (9:15 AM to 3:30 PM)
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_start <= now <= market_end
    
    def save_friday_data(self):
        """Save current data as Friday cache (called on Friday at 3:30 PM)"""
        try:
            # Source file
            current_file = os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                       'historical_breadth_data', 'sma_breadth_historical_latest.json')
            
            # Copy current data to Friday cache
            if os.path.exists(current_file):
                shutil.copy2(current_file, self.friday_data_path)
                self.logger.info(f"Friday data cached at {self.friday_data_path}")
                
                # Also save a timestamped version
                timestamp = datetime.now(self.ist).strftime('%Y%m%d_%H%M%S')
                timestamped_path = self.friday_data_path.replace('.json', f'_{timestamp}.json')
                shutil.copy2(current_file, timestamped_path)
                
        except Exception as e:
            self.logger.error(f"Error saving Friday data: {e}")
    
    def get_data_source(self) -> str:
        """Determine which data source to use based on current time"""
        now = datetime.now(self.ist)
        
        # If weekend, use Friday cache
        if now.weekday() > 4:  # Saturday or Sunday
            if os.path.exists(self.friday_data_path):
                return self.friday_data_path
            else:
                self.logger.warning("Friday cache not found, using latest data")
                return os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                                  'historical_breadth_data', 'sma_breadth_historical_latest.json')
        
        # If weekday but outside market hours
        if not self.is_market_hours():
            # If it's Monday morning before 9:15, use Friday cache
            if now.weekday() == 0 and now.hour < 9:
                if os.path.exists(self.friday_data_path):
                    return self.friday_data_path
        
        # Default to latest data
        return os.path.join(self.base_dir, 'Daily', 'Market_Regime', 
                           'historical_breadth_data', 'sma_breadth_historical_latest.json')
    
    def get_ml_insights(self) -> Dict:
        """Get ML insights with scheduled data awareness"""
        try:
            # Add data source info to response
            data_source = self.get_data_source()
            is_cached = 'friday_cache' in data_source
            
            # Get base insights
            insights = super().get_ml_insights()
            
            # Add scheduling metadata
            insights['data_metadata'] = {
                'is_market_hours': self.is_market_hours(),
                'data_source': 'friday_cache' if is_cached else 'live_data',
                'current_time': datetime.now(self.ist).isoformat(),
                'using_cached_data': is_cached
            }
            
            # Add warning if using cached data
            if is_cached:
                insights['data_metadata']['cache_warning'] = "Using Friday 3:30 PM data (market closed)"
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting scheduled ML insights: {e}")
            return super().get_ml_insights()

def create_friday_cache_scheduler():
    """Create a scheduler to save Friday data at 3:30 PM"""
    import schedule
    import time
    
    integration = ScheduledMLDashboardIntegration()
    
    # Schedule Friday data save at 3:30 PM
    schedule.every().friday.at("15:30").do(integration.save_friday_data)
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

# Flask route helpers that override the original ones
def get_ml_insights():
    """Flask route helper to get ML insights with scheduling"""
    integration = ScheduledMLDashboardIntegration()
    return integration.get_ml_insights()

def get_ml_alerts():
    """Flask route helper to get ML alerts"""
    integration = ScheduledMLDashboardIntegration()
    return integration.get_ml_alerts()

def get_ml_performance():
    """Flask route helper to get ML performance metrics"""
    integration = ScheduledMLDashboardIntegration()
    return integration.get_ml_performance_metrics()

if __name__ == "__main__":
    # Test the scheduled integration
    integration = ScheduledMLDashboardIntegration()
    
    print("Scheduled ML Dashboard Integration Test")
    print("-" * 60)
    
    # Check current status
    print(f"Is Market Hours: {integration.is_market_hours()}")
    print(f"Data Source: {integration.get_data_source()}")
    
    # Get insights
    insights = integration.get_ml_insights()
    print(f"\nData Metadata: {insights.get('data_metadata', {})}")
    print(f"Strategy: {insights['strategy']['recommended']}")
    print(f"Confidence: {insights['strategy']['confidence']:.2f}")