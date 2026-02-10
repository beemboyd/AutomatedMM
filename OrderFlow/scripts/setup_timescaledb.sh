#!/bin/bash
# Setup TimescaleDB for OrderFlow module
# Usage: ./setup_timescaledb.sh

set -e

echo "=== OrderFlow TimescaleDB Setup ==="

# Step 1: Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL via Homebrew..."
    brew install postgresql@16
    brew services start postgresql@16
    echo "Waiting for PostgreSQL to start..."
    sleep 5
else
    echo "PostgreSQL already installed: $(psql --version)"
fi

# Step 2: Check if TimescaleDB extension is installed
if ! brew list timescaledb 2>/dev/null; then
    echo "Installing TimescaleDB..."
    brew tap timescale/tap
    brew install timescaledb

    # Run timescaledb-tune to configure PostgreSQL
    echo "Running timescaledb-tune..."
    timescaledb-tune --quiet --yes

    # Restart PostgreSQL to load the extension
    brew services restart postgresql@16
    sleep 5
else
    echo "TimescaleDB already installed"
fi

# Step 3: Create the orderflow database
echo "Creating orderflow database..."
createdb orderflow 2>/dev/null || echo "Database 'orderflow' already exists"

# Step 4: Enable TimescaleDB extension
echo "Enabling TimescaleDB extension..."
psql -d orderflow -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;" 2>/dev/null

# Step 5: Apply schema
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_FILE="${SCRIPT_DIR}/../config/schema.sql"

if [ -f "${SCHEMA_FILE}" ]; then
    echo "Applying schema from ${SCHEMA_FILE}..."
    psql -d orderflow -f "${SCHEMA_FILE}"
    echo "Schema applied successfully"
else
    echo "ERROR: Schema file not found at ${SCHEMA_FILE}"
    exit 1
fi

# Step 6: Verify setup
echo ""
echo "=== Verification ==="
psql -d orderflow -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
psql -d orderflow -c "SELECT hypertable_name FROM timescaledb_information.hypertables;"
echo ""
echo "=== TimescaleDB Setup Complete ==="
