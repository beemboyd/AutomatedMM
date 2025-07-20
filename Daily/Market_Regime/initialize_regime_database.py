#!/usr/bin/env python
"""
Initialize the regime learning database with required tables
"""

import sqlite3
import os

def initialize_database():
    """Create the predictions and regime_changes tables"""
    
    # Database path
    db_path = "/Users/maverick/PycharmProjects/India-TS/data/regime_learning.db"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create predictions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            regime TEXT,
            confidence REAL,
            market_score REAL,
            trend_score REAL,
            momentum_score REAL,
            volatility_score REAL,
            breadth_score REAL,
            indicators TEXT,
            reasoning TEXT,
            UNIQUE(timestamp)
        )
    """)
    
    # Create regime_changes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS regime_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            from_regime TEXT,
            to_regime TEXT,
            confidence REAL,
            trigger_reason TEXT
        )
    """)
    
    # Create index for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_predictions_timestamp 
        ON predictions(timestamp DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_regime_changes_timestamp 
        ON regime_changes(timestamp DESC)
    """)
    
    # Commit changes
    conn.commit()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    print("Database initialized successfully!")
    print(f"Database location: {db_path}")
    print(f"Tables created: {[t[0] for t in tables]}")
    
    conn.close()

if __name__ == "__main__":
    initialize_database()