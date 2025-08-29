#!/usr/bin/env python3
"""
Feature Store Module
Centralized storage for features with versioning and consistency management
Ensures same features are used for training and inference
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import glob
import sqlite3
from typing import Dict, List, Optional, Tuple
import hashlib

# Setup logging
log_dir = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/logs'
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{log_dir}/feature_store.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FeatureStore:
    """
    Manages feature storage, versioning, and retrieval
    Key capabilities:
    1. Store features with version control
    2. Track feature lineage and transformations
    3. Ensure consistency between training and serving
    4. Cache computed features for efficiency
    """
    
    def __init__(self):
        self.store_path = '/Users/maverick/PycharmProjects/India-TS/Daily/New_Market_Regime/data/features'
        self.metadata_db = f'{self.store_path}/feature_metadata.db'
        
        # Create directories
        os.makedirs(self.store_path, exist_ok=True)
        
        # Initialize metadata database
        self._init_metadata_db()
        
        # Feature schema tracking
        self.current_schema = None
        self.schema_version = None
        
    def _init_metadata_db(self):
        """
        Initialize SQLite database for feature metadata
        """
        conn = sqlite3.connect(self.metadata_db)
        cursor = conn.cursor()
        
        # Feature versions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_versions (
                version_id TEXT PRIMARY KEY,
                created_at TIMESTAMP,
                feature_count INTEGER,
                feature_names TEXT,
                schema_hash TEXT,
                data_source TEXT,
                is_active BOOLEAN,
                performance_score REAL,
                notes TEXT
            )
        ''')
        
        # Feature usage tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_usage (
                usage_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id TEXT,
                used_at TIMESTAMP,
                usage_type TEXT,  -- 'training', 'inference', 'backtest'
                model_version TEXT,
                results TEXT,
                FOREIGN KEY (version_id) REFERENCES feature_versions(version_id)
            )
        ''')
        
        # Feature statistics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id TEXT,
                feature_name TEXT,
                mean REAL,
                std REAL,
                min REAL,
                max REAL,
                missing_count INTEGER,
                unique_count INTEGER,
                computed_at TIMESTAMP,
                FOREIGN KEY (version_id) REFERENCES feature_versions(version_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("Feature metadata database initialized")
    
    def register_features(self, features_df: pd.DataFrame, 
                         source: str = "unknown",
                         notes: str = None) -> str:
        """
        Register a new feature set in the store
        """
        try:
            # Generate version ID
            version_id = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Calculate schema hash
            feature_names = sorted([col for col in features_df.columns 
                                  if col not in ['timestamp', 'data_quality']])
            schema_hash = hashlib.md5(
                json.dumps(feature_names).encode()
            ).hexdigest()
            
            # Save features to parquet
            feature_file = f"{self.store_path}/features_v{version_id}.parquet"
            features_df.to_parquet(feature_file)
            
            # Calculate feature statistics
            self._calculate_feature_stats(features_df, version_id)
            
            # Register in metadata database
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO feature_versions 
                (version_id, created_at, feature_count, feature_names, 
                 schema_hash, data_source, is_active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                version_id,
                datetime.now(),
                len(feature_names),
                json.dumps(feature_names),
                schema_hash,
                source,
                True,  # New versions are active by default
                notes
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Registered feature version: {version_id}")
            logger.info(f"Schema hash: {schema_hash}")
            logger.info(f"Features: {len(feature_names)}")
            
            # Update current schema
            self.current_schema = feature_names
            self.schema_version = version_id
            
            return version_id
            
        except Exception as e:
            logger.error(f"Error registering features: {e}")
            return None
    
    def _calculate_feature_stats(self, features_df: pd.DataFrame, version_id: str):
        """
        Calculate and store statistics for each feature
        """
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            for col in features_df.columns:
                if col in ['timestamp', 'data_quality']:
                    continue
                
                series = features_df[col]
                
                # Handle non-numeric columns
                if not pd.api.types.is_numeric_dtype(series):
                    stats = {
                        'mean': None,
                        'std': None,
                        'min': None,
                        'max': None,
                        'missing_count': series.isna().sum(),
                        'unique_count': series.nunique()
                    }
                else:
                    stats = {
                        'mean': series.mean(),
                        'std': series.std(),
                        'min': series.min(),
                        'max': series.max(),
                        'missing_count': series.isna().sum(),
                        'unique_count': series.nunique()
                    }
                
                cursor.execute('''
                    INSERT INTO feature_stats 
                    (version_id, feature_name, mean, std, min, max, 
                     missing_count, unique_count, computed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    version_id,
                    col,
                    stats['mean'],
                    stats['std'],
                    stats['min'],
                    stats['max'],
                    stats['missing_count'],
                    stats['unique_count'],
                    datetime.now()
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error calculating feature stats: {e}")
    
    def get_features(self, version_id: str = None, 
                    latest: bool = True) -> pd.DataFrame:
        """
        Retrieve features from the store
        """
        try:
            if version_id:
                # Load specific version
                feature_file = f"{self.store_path}/features_v{version_id}.parquet"
            elif latest:
                # Load latest active version
                conn = sqlite3.connect(self.metadata_db)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT version_id FROM feature_versions 
                    WHERE is_active = 1 
                    ORDER BY created_at DESC 
                    LIMIT 1
                ''')
                
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    logger.error("No active feature version found")
                    return None
                
                version_id = result[0]
                feature_file = f"{self.store_path}/features_v{version_id}.parquet"
            else:
                logger.error("Must specify version_id or latest=True")
                return None
            
            if not os.path.exists(feature_file):
                logger.error(f"Feature file not found: {feature_file}")
                return None
            
            features_df = pd.read_parquet(feature_file)
            
            # Log usage
            self._log_feature_usage(version_id, 'retrieval')
            
            logger.info(f"Retrieved features version: {version_id}")
            return features_df
            
        except Exception as e:
            logger.error(f"Error retrieving features: {e}")
            return None
    
    def _log_feature_usage(self, version_id: str, usage_type: str, 
                          model_version: str = None, results: Dict = None):
        """
        Track feature usage for lineage
        """
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO feature_usage 
                (version_id, used_at, usage_type, model_version, results)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                version_id,
                datetime.now(),
                usage_type,
                model_version,
                json.dumps(results) if results else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging feature usage: {e}")
    
    def validate_schema(self, features_df: pd.DataFrame, 
                       version_id: str = None) -> bool:
        """
        Validate that features match expected schema
        """
        try:
            # Get expected schema
            if version_id:
                conn = sqlite3.connect(self.metadata_db)
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT feature_names FROM feature_versions 
                    WHERE version_id = ?
                ''', (version_id,))
                
                result = cursor.fetchone()
                conn.close()
                
                if not result:
                    logger.error(f"Version {version_id} not found")
                    return False
                
                expected_features = json.loads(result[0])
            elif self.current_schema:
                expected_features = self.current_schema
            else:
                logger.warning("No schema to validate against")
                return True
            
            # Check current features
            current_features = sorted([col for col in features_df.columns 
                                      if col not in ['timestamp', 'data_quality']])
            
            # Compare
            missing = set(expected_features) - set(current_features)
            extra = set(current_features) - set(expected_features)
            
            if missing:
                logger.error(f"Missing features: {missing}")
                return False
            
            if extra:
                logger.warning(f"Extra features (will be ignored): {extra}")
            
            logger.info("Schema validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating schema: {e}")
            return False
    
    def get_feature_importance(self, model_version: str) -> pd.DataFrame:
        """
        Get feature importance scores from model training
        """
        try:
            conn = sqlite3.connect(self.metadata_db)
            
            query = '''
                SELECT fu.version_id, fu.results 
                FROM feature_usage fu
                WHERE fu.usage_type = 'training' 
                AND fu.model_version = ?
                ORDER BY fu.used_at DESC
                LIMIT 1
            '''
            
            df = pd.read_sql_query(query, conn, params=(model_version,))
            conn.close()
            
            if len(df) == 0:
                logger.warning(f"No training results found for model {model_version}")
                return None
            
            # Parse results JSON
            results = json.loads(df.iloc[0]['results'])
            
            if 'feature_importance' in results:
                importance_df = pd.DataFrame(results['feature_importance'])
                return importance_df.sort_values('importance', ascending=False)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting feature importance: {e}")
            return None
    
    def compare_versions(self, version1: str, version2: str) -> Dict:
        """
        Compare two feature versions
        """
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Get metadata for both versions
            cursor.execute('''
                SELECT version_id, feature_names, schema_hash, created_at 
                FROM feature_versions 
                WHERE version_id IN (?, ?)
            ''', (version1, version2))
            
            results = cursor.fetchall()
            conn.close()
            
            if len(results) != 2:
                logger.error("Could not find both versions")
                return None
            
            # Parse results
            versions = {}
            for row in results:
                versions[row[0]] = {
                    'features': json.loads(row[1]),
                    'schema_hash': row[2],
                    'created_at': row[3]
                }
            
            # Compare
            features1 = set(versions[version1]['features'])
            features2 = set(versions[version2]['features'])
            
            comparison = {
                'version1': version1,
                'version2': version2,
                'schema_match': versions[version1]['schema_hash'] == versions[version2]['schema_hash'],
                'added_features': list(features2 - features1),
                'removed_features': list(features1 - features2),
                'common_features': list(features1 & features2),
                'feature_count_diff': len(features2) - len(features1)
            }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            return None
    
    def cleanup_old_versions(self, keep_days: int = 30):
        """
        Remove old feature versions to save space
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Find old inactive versions
            cursor.execute('''
                SELECT version_id FROM feature_versions 
                WHERE created_at < ? AND is_active = 0
            ''', (cutoff_date,))
            
            old_versions = cursor.fetchall()
            
            for (version_id,) in old_versions:
                # Delete feature file
                feature_file = f"{self.store_path}/features_v{version_id}.parquet"
                if os.path.exists(feature_file):
                    os.remove(feature_file)
                    logger.info(f"Removed old feature file: {feature_file}")
                
                # Delete from database
                cursor.execute('DELETE FROM feature_versions WHERE version_id = ?', (version_id,))
                cursor.execute('DELETE FROM feature_stats WHERE version_id = ?', (version_id,))
                cursor.execute('DELETE FROM feature_usage WHERE version_id = ?', (version_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {len(old_versions)} old versions")
            
        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
    
    def get_store_summary(self) -> Dict:
        """
        Get summary of feature store
        """
        try:
            conn = sqlite3.connect(self.metadata_db)
            cursor = conn.cursor()
            
            # Count versions
            cursor.execute('SELECT COUNT(*) FROM feature_versions')
            total_versions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM feature_versions WHERE is_active = 1')
            active_versions = cursor.fetchone()[0]
            
            # Get latest version
            cursor.execute('''
                SELECT version_id, created_at, feature_count 
                FROM feature_versions 
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            latest = cursor.fetchone()
            
            # Get usage stats
            cursor.execute('''
                SELECT usage_type, COUNT(*) as count 
                FROM feature_usage 
                GROUP BY usage_type
            ''')
            usage_stats = dict(cursor.fetchall())
            
            conn.close()
            
            # Calculate storage size
            total_size = 0
            for file in glob.glob(f"{self.store_path}/*.parquet"):
                total_size += os.path.getsize(file)
            
            summary = {
                'total_versions': total_versions,
                'active_versions': active_versions,
                'latest_version': latest[0] if latest else None,
                'latest_created': latest[1] if latest else None,
                'latest_features': latest[2] if latest else 0,
                'usage_stats': usage_stats,
                'storage_size_mb': total_size / (1024 * 1024)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting store summary: {e}")
            return None


def main():
    """
    Test feature store functionality
    """
    store = FeatureStore()
    
    # Get store summary
    summary = store.get_store_summary()
    
    print("\n" + "=" * 50)
    print("Feature Store Summary:")
    print("=" * 50)
    
    if summary:
        print(f"Total versions: {summary['total_versions']}")
        print(f"Active versions: {summary['active_versions']}")
        print(f"Storage size: {summary['storage_size_mb']:.2f} MB")
        
        if summary['latest_version']:
            print(f"\nLatest version: {summary['latest_version']}")
            print(f"Created: {summary['latest_created']}")
            print(f"Features: {summary['latest_features']}")
        
        if summary['usage_stats']:
            print("\nUsage statistics:")
            for usage_type, count in summary['usage_stats'].items():
                print(f"  {usage_type}: {count}")
    else:
        print("No data in feature store yet")
    
    print("\n✅ Feature store is ready!")


if __name__ == "__main__":
    main()