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


def apply_migrations(db_config):
    """Apply schema migrations to existing tables (idempotent)"""
    conn = get_connection(db_config)
    conn.autocommit = True
    cursor = conn.cursor()

    # ── Migration 1: Add enhanced metrics columns to of_metrics ──
    new_columns = [
        ("bid_ask_ratio",       "DOUBLE PRECISION"),
        ("net_liquidity_delta", "BIGINT DEFAULT 0"),
        ("spread",              "DOUBLE PRECISION"),
        ("best_bid_qty",        "BIGINT DEFAULT 0"),
        ("best_ask_qty",        "BIGINT DEFAULT 0"),
        ("delta_per_trade",     "DOUBLE PRECISION"),
        ("cvd_slope",           "DOUBLE PRECISION"),
        ("buy_sell_ratio",      "DOUBLE PRECISION"),
        ("buying_pressure",     "DOUBLE PRECISION DEFAULT 0"),
        ("selling_pressure",    "DOUBLE PRECISION DEFAULT 0"),
        ("divergence_score",    "DOUBLE PRECISION DEFAULT 0"),
    ]

    for col_name, col_type in new_columns:
        try:
            cursor.execute(
                f"ALTER TABLE of_metrics ADD COLUMN {col_name} {col_type};"
            )
            logger.info(f"Added column: of_metrics.{col_name}")
        except psycopg2.errors.DuplicateColumn:
            logger.debug(f"Column of_metrics.{col_name} already exists, skipping")

    # ── Migration 2: Change delta_divergence from BOOLEAN to DOUBLE PRECISION ──
    # Check current type
    cursor.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name = 'of_metrics' AND column_name = 'delta_divergence'
    """)
    row = cursor.fetchone()
    if row and row[0] == 'boolean':
        logger.info("Migrating delta_divergence from BOOLEAN to DOUBLE PRECISION...")
        # Drop the boolean default first, then change type, then set new default
        cursor.execute("""
            ALTER TABLE of_metrics ALTER COLUMN delta_divergence DROP DEFAULT;
        """)
        cursor.execute("""
            ALTER TABLE of_metrics
            ALTER COLUMN delta_divergence TYPE DOUBLE PRECISION
            USING CASE WHEN delta_divergence THEN 1.0 ELSE 0.0 END;
        """)
        cursor.execute("""
            ALTER TABLE of_metrics ALTER COLUMN delta_divergence SET DEFAULT 0;
        """)
        logger.info("Migrated delta_divergence to DOUBLE PRECISION")

    # ── Migration 3: Recreate of_metrics_1min materialized view ──
    logger.info("Recreating of_metrics_1min materialized view...")
    cursor.execute("DROP MATERIALIZED VIEW IF EXISTS of_metrics_1min CASCADE;")

    cursor.execute("""
        CREATE MATERIALIZED VIEW of_metrics_1min AS
        SELECT
            date_trunc('minute', ts) AS bucket,
            symbol,
            SUM(trade_delta) AS delta_1m,
            (array_agg(cumulative_delta ORDER BY ts DESC))[1] AS cvd,
            AVG(bid_ask_imbalance_l5) AS avg_imbalance,
            SUM(interval_volume) AS volume_1m,
            SUM(large_trade_count) AS large_trades,
            (array_agg(phase ORDER BY ts DESC))[1] AS phase,
            (array_agg(price_open ORDER BY ts ASC))[1] AS open,
            MAX(price_high) AS high,
            MIN(price_low) AS low,
            (array_agg(price_close ORDER BY ts DESC))[1] AS close,
            AVG(buying_pressure) AS avg_buying_pressure,
            AVG(selling_pressure) AS avg_selling_pressure,
            (array_agg(divergence_score ORDER BY ts DESC))[1] AS divergence_score,
            AVG(bid_ask_ratio) AS avg_bid_ask_ratio,
            (array_agg(cvd_slope ORDER BY ts DESC))[1] AS cvd_slope
        FROM of_metrics
        GROUP BY bucket, symbol;
    """)
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_of_metrics_1min_pk "
        "ON of_metrics_1min (bucket, symbol);"
    )
    logger.info("Materialized view of_metrics_1min recreated with enhanced columns")

    cursor.close()
    conn.close()
    logger.info("Migrations applied successfully")


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
    apply_migrations(db_config)
    verify_setup(db_config)


if __name__ == "__main__":
    main()
