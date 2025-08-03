#!/usr/bin/env python
"""
Model Manager for Market Regime Predictor
=========================================
Handles model persistence, versioning, and performance tracking.
"""

import os
import json
import pickle
import shutil
import logging
from datetime import datetime
import numpy as np
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelManager:
    """Manages ML models for market regime prediction"""
    
    def __init__(self, models_dir=None):
        """Initialize model manager"""
        if models_dir is None:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            self.models_dir = os.path.join(self.script_dir, "models")
        else:
            self.models_dir = models_dir
            
        # Ensure directories exist
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(os.path.join(self.models_dir, "archive"), exist_ok=True)
        
        # Model metadata file
        self.metadata_file = os.path.join(self.models_dir, "model_metadata.json")
        self.metadata = self._load_metadata()
        
    def _load_metadata(self):
        """Load model metadata"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except:
                return self._initialize_metadata()
        return self._initialize_metadata()
        
    def _initialize_metadata(self):
        """Initialize metadata structure"""
        return {
            'current_version': None,
            'versions': {},
            'performance_history': [],
            'best_model': None
        }
        
    def save_model(self, model, scaler, performance_metrics, version_name=None):
        """Save model with versioning and metadata"""
        try:
            # Generate version name if not provided
            if version_name is None:
                version_name = f"v_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
            # Create version directory
            version_dir = os.path.join(self.models_dir, version_name)
            os.makedirs(version_dir, exist_ok=True)
            
            # Save model and scaler
            model_path = os.path.join(version_dir, "model.pkl")
            scaler_path = os.path.join(version_dir, "scaler.pkl")
            
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
                
            with open(scaler_path, 'wb') as f:
                pickle.dump(scaler, f)
                
            # Save performance metrics
            metrics_path = os.path.join(version_dir, "metrics.json")
            with open(metrics_path, 'w') as f:
                json.dump(performance_metrics, f, indent=2)
                
            # Update metadata
            self.metadata['versions'][version_name] = {
                'created': datetime.now().isoformat(),
                'model_path': model_path,
                'scaler_path': scaler_path,
                'metrics_path': metrics_path,
                'performance': performance_metrics.get('accuracy', 0),
                'total_predictions': performance_metrics.get('total_predictions', 0)
            }
            
            # Set as current version
            self.metadata['current_version'] = version_name
            
            # Check if this is the best model
            if (self.metadata['best_model'] is None or 
                performance_metrics.get('accuracy', 0) > 
                self.metadata['versions'].get(self.metadata['best_model'], {}).get('performance', 0)):
                self.metadata['best_model'] = version_name
                
            # Save metadata
            self._save_metadata()
            
            # Also save to standard locations for compatibility
            shutil.copy(model_path, os.path.join(self.models_dir, "regime_predictor_model.pkl"))
            shutil.copy(scaler_path, os.path.join(self.models_dir, "regime_predictor_scaler.pkl"))
            
            logger.info(f"Model saved as version {version_name} with accuracy {performance_metrics.get('accuracy', 0):.2%}")
            
            return version_name
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return None
            
    def load_model(self, version_name=None):
        """Load model by version name"""
        try:
            # Use current version if not specified
            if version_name is None:
                version_name = self.metadata.get('current_version')
                
            if version_name is None or version_name not in self.metadata['versions']:
                logger.warning("No valid model version found")
                return None, None
                
            version_info = self.metadata['versions'][version_name]
            
            # Load model
            with open(version_info['model_path'], 'rb') as f:
                model = pickle.load(f)
                
            # Load scaler
            with open(version_info['scaler_path'], 'rb') as f:
                scaler = pickle.load(f)
                
            logger.info(f"Loaded model version {version_name}")
            return model, scaler
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return None, None
            
    def load_best_model(self):
        """Load the best performing model"""
        best_version = self.metadata.get('best_model')
        if best_version:
            return self.load_model(best_version)
        return self.load_model()  # Fall back to current version
        
    def get_model_info(self, version_name=None):
        """Get information about a model version"""
        if version_name is None:
            version_name = self.metadata.get('current_version')
            
        if version_name in self.metadata['versions']:
            return self.metadata['versions'][version_name]
        return None
        
    def list_versions(self):
        """List all available model versions"""
        versions = []
        for version_name, info in self.metadata['versions'].items():
            versions.append({
                'version': version_name,
                'created': info['created'],
                'performance': info['performance'],
                'predictions': info['total_predictions'],
                'is_current': version_name == self.metadata['current_version'],
                'is_best': version_name == self.metadata['best_model']
            })
        return sorted(versions, key=lambda x: x['created'], reverse=True)
        
    def archive_old_models(self, keep_last_n=5):
        """Archive old model versions, keeping only the last N and the best model"""
        try:
            versions = self.list_versions()
            
            # Always keep current and best models
            keep_versions = {self.metadata['current_version'], self.metadata['best_model']}
            
            # Keep last N versions
            for version in versions[:keep_last_n]:
                keep_versions.add(version['version'])
                
            # Archive others
            for version_name in list(self.metadata['versions'].keys()):
                if version_name not in keep_versions:
                    # Move to archive
                    version_dir = os.path.join(self.models_dir, version_name)
                    archive_dir = os.path.join(self.models_dir, "archive", version_name)
                    
                    if os.path.exists(version_dir):
                        shutil.move(version_dir, archive_dir)
                        
                    # Remove from metadata
                    del self.metadata['versions'][version_name]
                    logger.info(f"Archived model version {version_name}")
                    
            self._save_metadata()
            
        except Exception as e:
            logger.error(f"Error archiving models: {e}")
            
    def _save_metadata(self):
        """Save metadata to file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            
    def compare_models(self, version1, version2):
        """Compare performance of two model versions"""
        info1 = self.get_model_info(version1)
        info2 = self.get_model_info(version2)
        
        if not info1 or not info2:
            return None
            
        # Load full metrics
        with open(info1['metrics_path'], 'r') as f:
            metrics1 = json.load(f)
            
        with open(info2['metrics_path'], 'r') as f:
            metrics2 = json.load(f)
            
        comparison = {
            'version1': {
                'name': version1,
                'accuracy': info1['performance'],
                'predictions': info1['total_predictions'],
                'regime_accuracy': metrics1.get('regime_accuracy', {})
            },
            'version2': {
                'name': version2,
                'accuracy': info2['performance'],
                'predictions': info2['total_predictions'],
                'regime_accuracy': metrics2.get('regime_accuracy', {})
            },
            'accuracy_diff': info2['performance'] - info1['performance'],
            'better_model': version2 if info2['performance'] > info1['performance'] else version1
        }
        
        return comparison
        
    def get_performance_trend(self, last_n_versions=10):
        """Get performance trend across model versions"""
        versions = self.list_versions()[:last_n_versions]
        
        trend = []
        for version in reversed(versions):  # Oldest to newest
            trend.append({
                'version': version['version'],
                'date': version['created'],
                'accuracy': version['performance'],
                'predictions': version['predictions']
            })
            
        return trend


def main():
    """Test model manager functionality"""
    manager = ModelManager()
    
    print("\n" + "="*60)
    print("MODEL MANAGER TEST")
    print("="*60)
    
    # List available versions
    print("\nAvailable Model Versions:")
    versions = manager.list_versions()
    
    if versions:
        for v in versions:
            status = []
            if v['is_current']:
                status.append("CURRENT")
            if v['is_best']:
                status.append("BEST")
            status_str = f" [{', '.join(status)}]" if status else ""
            
            print(f"  {v['version']}: {v['performance']:.2%} accuracy "
                  f"({v['predictions']} predictions){status_str}")
    else:
        print("  No models found")
        
    # Get performance trend
    trend = manager.get_performance_trend()
    if trend:
        print("\nPerformance Trend:")
        for t in trend:
            print(f"  {t['date'][:10]}: {t['accuracy']:.2%}")
            
    print("\n" + "="*60)


if __name__ == "__main__":
    main()