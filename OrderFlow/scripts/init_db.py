#!/usr/bin/env python3
"""
Programmatic TimescaleDB schema initialization for OrderFlow module.
Creates database, extension, tables, hypertables, and policies.

Usage: python init_db.py [--drop-existing]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Paths
MODULE_DIR = Path(__file__).parent.parent
CONFIG_FILE = MODULE_DIR / "config" / "orderflow_config.json"
SCHEMA_FILE = MODULE_DIR / "config" / "schema.sql"


def load_config():
    """Load database config from orderflow_config.json"""
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("db", {})


def create_database(db_config):
    """Create the orderflow database if it doesn't exist"""
    conn = psycopg2.connect(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 5432),
        user=db_config.get("user", "maverick"),
        password=db_config.get("password", ""),
        dbname="postgres"
    )
    conn.autocommit = True
    cursor = conn.cursor()

    db_name = db_config.get("name", "orderflow")

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
    if not cursor.fetchone():
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
        logger.info(f"Created database '{db_name}'")
    else:
        logger.info(f"Database '{db_name}' already exists")

    cursor.close()
    conn.close()


def get_connection(db_config):
    """Get a connection to the orderflow database"""
    return psycopg2.connect(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 5432),
        user=db_config.get("user", "maverick"),
        password=db_config.get("password", ""),
        dbname=db_config.get("name", "orderflow")
    )


def drop_existing(db_config):
    """Drop all existing tables (for fresh re-initialization)"""
    conn = get_connection(db_config)
    conn.autocommit = True
    cursor = conn.cursor()

    views = ["orderflow_1min"]
    tables = ["orderflow_metrics", "depth_snapshots", "raw_ticks"]

    for view in views:
        cursor.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view} CASCADE;")
        logger.info(f"Dropped materialized view: {view}")

    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
        logger.info(f"Dropped table: {table}")

    cursor.close()
    conn.close()


def apply_schema(db_config):
    """Apply the SQL schema file"""
    conn = get_connection(db_config)
    conn.autocommit = True
    cursor = conn.cursor()

    # Enable TimescaleDB extension
    cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    logger.info("TimescaleDB extension enabled")

    # Read and execute schema
    schema_sql = SCHEMA_FILE.read_text()

    # Split on semicolons and execute statements individually
    # (needed because some statements are SELECT calls that return values)
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

    for stmt in statements:
        # Skip pure comments
        lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
        clean = '\n'.join(lines).strip()
        if not clean:
            continue

        try:
            cursor.execute(clean + ';')
            logger.debug(f"Executed: {clean[:80]}...")
        except psycopg2.errors.DuplicateTable:
            logger.info(f"Table/view already exists, skipping")
        except psycopg2.errors.DuplicateObject:
            logger.info(f"Object already exists, skipping")
        except Exception as e:
            # Log but continue for non-critical errors (e.g. policy already exists)
            logger.warning(f"Statement warning: {e}")

    cursor.close()
    conn.close()
    logger.info("Schema applied successfully")


def verify_setup(db_config):
    """Verify tables and hypertables exist"""
    conn = get_connection(db_config)
    cursor = conn.cursor()

    # Check TimescaleDB version
    cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';")
    row = cursor.fetchone()
    logger.info(f"TimescaleDB version: {row[0] if row else 'NOT INSTALLED'}")

    # Check hypertables
    cursor.execute("SELECT hypertable_name FROM timescaledb_information.hypertables;")
    hypertables = [r[0] for r in cursor.fetchall()]
    logger.info(f"Hypertables: {hypertables}")

    expected = {"raw_ticks", "depth_snapshots", "orderflow_metrics"}
    missing = expected - set(hypertables)
    if missing:
        logger.error(f"Missing hypertables: {missing}")
        return False

    # Check materialized views
    cursor.execute("""
        SELECT view_name FROM timescaledb_information.continuous_aggregates;
    """)
    views = [r[0] for r in cursor.fetchall()]
    logger.info(f"Continuous aggregates: {views}")

    cursor.close()
    conn.close()
    logger.info("Verification complete - all tables present")
    return True


def main():
    parser = argparse.ArgumentParser(description="Initialize OrderFlow TimescaleDB schema")
    parser.add_argument("--drop-existing", action="store_true",
                        help="Drop all existing tables before re-creating")
    args = parser.parse_args()

    db_config = load_config()
    logger.info(f"Database: {db_config.get('name')} @ {db_config.get('host')}:{db_config.get('port')}")

    create_database(db_config)

    if args.drop_existing:
        logger.warning("Dropping existing tables...")
        drop_existing(db_config)

    apply_schema(db_config)
    verify_setup(db_config)


if __name__ == "__main__":
    main()
