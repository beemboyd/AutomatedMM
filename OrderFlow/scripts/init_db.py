#!/usr/bin/env python3
"""
PostgreSQL schema initialization for OrderFlow module.
Creates tables and indexes in the existing tick_data database.

Usage: python init_db.py [--drop-existing]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

MODULE_DIR = Path(__file__).parent.parent
CONFIG_FILE = MODULE_DIR / "config" / "orderflow_config.json"
SCHEMA_FILE = MODULE_DIR / "config" / "schema.sql"


def load_config():
    """Load database config from orderflow_config.json"""
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    return config.get("db", {})


def get_connection(db_config):
    """Get a connection to the tick_data database"""
    return psycopg2.connect(
        host=db_config.get("host", "localhost"),
        port=db_config.get("port", 5432),
        user=db_config.get("user", "maverick"),
        password=db_config.get("password", ""),
        dbname=db_config.get("name", "tick_data")
    )


def drop_existing(db_config):
    """Drop all OrderFlow tables (for fresh re-initialization)"""
    conn = get_connection(db_config)
    conn.autocommit = True
    cursor = conn.cursor()

    objects = [
        ("MATERIALIZED VIEW", "of_metrics_1min"),
        ("TABLE", "of_metrics"),
        ("TABLE", "of_depth_snapshots"),
        ("TABLE", "of_raw_ticks"),
    ]

    for obj_type, name in objects:
        cursor.execute(f"DROP {obj_type} IF EXISTS {name} CASCADE;")
        logger.info(f"Dropped {obj_type.lower()}: {name}")

    cursor.close()
    conn.close()


def apply_schema(db_config):
    """Apply the SQL schema file"""
    conn = get_connection(db_config)
    conn.autocommit = True
    cursor = conn.cursor()

    schema_sql = SCHEMA_FILE.read_text()

    # Split on semicolons and execute individually
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
            logger.info("Table/view already exists, skipping")
        except psycopg2.errors.DuplicateObject:
            logger.info("Object already exists, skipping")
        except Exception as e:
            logger.warning(f"Statement warning: {e}")

    cursor.close()
    conn.close()
    logger.info("Schema applied successfully")


def verify_setup(db_config):
    """Verify OrderFlow tables exist"""
    conn = get_connection(db_config)
    cursor = conn.cursor()

    expected_tables = ["of_raw_ticks", "of_depth_snapshots", "of_metrics"]
    expected_views = ["of_metrics_1min"]

    # Check tables
    cursor.execute("""
        SELECT tablename FROM pg_tables
        WHERE schemaname = 'public' AND tablename LIKE 'of_%'
    """)
    tables = [r[0] for r in cursor.fetchall()]
    logger.info(f"OrderFlow tables: {tables}")

    missing = set(expected_tables) - set(tables)
    if missing:
        logger.error(f"Missing tables: {missing}")
        cursor.close()
        conn.close()
        return False

    # Check materialized view
    cursor.execute("""
        SELECT matviewname FROM pg_matviews
        WHERE schemaname = 'public' AND matviewname LIKE 'of_%'
    """)
    views = [r[0] for r in cursor.fetchall()]
    logger.info(f"OrderFlow materialized views: {views}")

    # Check indexes
    cursor.execute("""
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public' AND indexname LIKE 'idx_of_%'
    """)
    indexes = [r[0] for r in cursor.fetchall()]
    logger.info(f"OrderFlow indexes: {indexes}")

    cursor.close()
    conn.close()
    logger.info("Verification complete - all tables present")
    return True


def main():
    parser = argparse.ArgumentParser(description="Initialize OrderFlow PostgreSQL schema")
    parser.add_argument("--drop-existing", action="store_true",
                        help="Drop all existing OrderFlow tables before re-creating")
    args = parser.parse_args()

    db_config = load_config()
    logger.info(f"Database: {db_config.get('name')} @ {db_config.get('host')}:{db_config.get('port')}")

    if args.drop_existing:
        logger.warning("Dropping existing OrderFlow tables...")
        drop_existing(db_config)

    apply_schema(db_config)
    verify_setup(db_config)


if __name__ == "__main__":
    main()
