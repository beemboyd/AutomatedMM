#!/usr/bin/env python3
"""
Fix Learning Database Schema

Creates missing tables and ensures database schema is correct.
"""

import sqlite3
import os
from datetime import datetime

def create_database_schema(db_path):
    """Create or update database schema"""
    print(f"Fixing database schema at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create predictions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            regime TEXT NOT NULL,
            confidence REAL NOT NULL,
            market_score REAL,
            trend_score REAL,
            momentum_score REAL,
            volatility_score REAL,
            breadth_score REAL,
            scanner_volatility_score REAL,
            scanner_volatility_regime TEXT,
            indicators TEXT,
            reasoning TEXT
        )
        """)
        print("✓ Created/verified predictions table")
        
        # Create feedback table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actual_regime TEXT,
            user_feedback TEXT,
            performance_score REAL,
            FOREIGN KEY (prediction_id) REFERENCES predictions(id)
        )
        """)
        print("✓ Created/verified feedback table")
        
        # Create regime_changes table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS regime_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            from_regime TEXT,
            to_regime TEXT,
            confidence REAL,
            trigger_indicators TEXT,
            market_conditions TEXT
        )
        """)
        print("✓ Created/verified regime_changes table")
        
        # Create performance_metrics table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE DEFAULT CURRENT_DATE,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            details TEXT
        )
        """)
        print("✓ Created/verified performance_metrics table")
        
        # Create model_parameters table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS model_parameters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parameter_name TEXT NOT NULL,
            parameter_value TEXT NOT NULL,
            parameter_type TEXT,
            description TEXT
        )
        """)
        print("✓ Created/verified model_parameters table")
        
        # Create indices for better performance
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_timestamp 
        ON predictions(timestamp)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_regime 
        ON predictions(regime)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_regime_changes_timestamp 
        ON regime_changes(timestamp)
        """)
        
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_metrics_date 
        ON performance_metrics(date)
        """)
        
        print("✓ Created/verified indices")
        
        # Insert initial model parameters if empty
        cursor.execute("SELECT COUNT(*) FROM model_parameters")
        param_count = cursor.fetchone()[0]
        
        if param_count == 0:
            initial_params = [
                ('confidence_threshold', '0.6', 'float', 'Minimum confidence for regime change'),
                ('lookback_window', '20', 'int', 'Days to look back for analysis'),
                ('volatility_weight', '0.2', 'float', 'Weight of volatility in regime calculation'),
                ('trend_weight', '0.3', 'float', 'Weight of trend in regime calculation'),
                ('momentum_weight', '0.3', 'float', 'Weight of momentum in regime calculation'),
                ('breadth_weight', '0.2', 'float', 'Weight of breadth in regime calculation'),
                ('scanner_integration', 'true', 'bool', 'Use scanner data for volatility'),
                ('learning_rate', '0.01', 'float', 'Model learning rate'),
                ('update_frequency', '300', 'int', 'Update frequency in seconds')
            ]
            
            cursor.executemany("""
            INSERT INTO model_parameters (parameter_name, parameter_value, parameter_type, description)
            VALUES (?, ?, ?, ?)
            """, initial_params)
            
            print("✓ Inserted initial model parameters")
        
        # Commit changes
        conn.commit()
        print("\n✅ Database schema fixed successfully!")
        
        # Display table info
        print("\nDatabase Tables:")
        cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' 
        ORDER BY name
        """)
        
        tables = cursor.fetchall()
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            print(f"  - {table[0]}: {count} records")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def migrate_existing_data(db_path):
    """Migrate any existing data from reports to database"""
    print("\nChecking for data migration...")
    
    reports_dir = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/reports"
    
    if not os.path.exists(reports_dir):
        print("No reports directory found")
        return
        
    import json
    import glob
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get existing prediction count
        cursor.execute("SELECT COUNT(*) FROM predictions")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"Database already has {existing_count} predictions. Skipping migration.")
            return
            
        # Get recent report files
        report_files = glob.glob(os.path.join(reports_dir, "regime_analysis_*.json"))
        report_files = [f for f in report_files if 'latest' not in f]
        report_files.sort()
        
        # Migrate last 100 reports
        recent_reports = report_files[-100:] if len(report_files) > 100 else report_files
        
        migrated = 0
        for report_file in recent_reports:
            try:
                with open(report_file, 'r') as f:
                    data = json.load(f)
                    
                if 'regime_analysis' in data:
                    analysis = data['regime_analysis']
                    indicators = analysis.get('indicators', {})
                    
                    cursor.execute("""
                    INSERT INTO predictions (
                        timestamp, regime, confidence, 
                        market_score, trend_score, momentum_score,
                        volatility_score, breadth_score,
                        scanner_volatility_score, scanner_volatility_regime,
                        indicators, reasoning
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        analysis.get('timestamp'),
                        analysis.get('regime'),
                        analysis.get('confidence', 0),
                        indicators.get('market_score'),
                        indicators.get('trend_score'),
                        indicators.get('momentum_composite'),
                        indicators.get('volatility_score'),
                        indicators.get('breadth_score'),
                        indicators.get('scanner_volatility_score'),
                        indicators.get('scanner_volatility_regime'),
                        json.dumps(indicators),
                        json.dumps(analysis.get('reasoning', []))
                    ))
                    
                    migrated += 1
                    
            except Exception as e:
                print(f"Error migrating {os.path.basename(report_file)}: {e}")
                
        conn.commit()
        print(f"✓ Migrated {migrated} predictions to database")
        
    except Exception as e:
        print(f"Migration error: {e}")
        conn.rollback()
        
    finally:
        conn.close()

def main():
    """Main execution"""
    db_path = "/Users/maverick/PycharmProjects/India-TS/Market_Regime/data/regime_learning.db"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    print("=" * 60)
    print("REGIME LEARNING DATABASE SCHEMA FIX")
    print("=" * 60)
    
    # Create/fix schema
    create_database_schema(db_path)
    
    # Migrate existing data
    migrate_existing_data(db_path)
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)

if __name__ == "__main__":
    main()