-- TG PnL Tracking Schema
-- Database: tick_data (shared with OrderFlow of_ tables)
-- Prefix: tg_ to avoid collisions

-- Table 1: Sessions — one row per bot engine start
CREATE TABLE IF NOT EXISTS tg_sessions (
    session_id      SERIAL PRIMARY KEY,
    bot_type        TEXT NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'active',
    config_snapshot JSONB,
    total_pnl       DOUBLE PRECISION DEFAULT 0,
    total_cycles    INTEGER DEFAULT 0,
    notes           TEXT
);

-- Table 2: Pairs — one row per primary-secondary combination per session
CREATE TABLE IF NOT EXISTS tg_pairs (
    pair_id         SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES tg_sessions(session_id),
    primary_ticker  TEXT NOT NULL,
    secondary_ticker TEXT,
    pair_type       TEXT NOT NULL DEFAULT 'hedged',
    anchor_price    DOUBLE PRECISION,
    grid_spacing    DOUBLE PRECISION,
    levels_per_side INTEGER,
    qty_per_level   INTEGER,
    product         TEXT DEFAULT 'CNC',
    pair_pnl        DOUBLE PRECISION DEFAULT 0,
    pair_cycles     INTEGER DEFAULT 0,
    UNIQUE (session_id, primary_ticker)
);

-- Table 3: Cycles — one row per complete grid round-trip
CREATE TABLE IF NOT EXISTS tg_cycles (
    cycle_id        SERIAL PRIMARY KEY,
    pair_id         INTEGER NOT NULL REFERENCES tg_pairs(pair_id),
    session_id      INTEGER NOT NULL REFERENCES tg_sessions(session_id),
    group_id        TEXT NOT NULL,
    bot_id          TEXT,
    grid_level      INTEGER,
    cycle_number    INTEGER DEFAULT 1,
    entry_side      TEXT NOT NULL,
    entry_price     DOUBLE PRECISION,
    entry_fill_price DOUBLE PRECISION,
    target_price    DOUBLE PRECISION,
    target_fill_price DOUBLE PRECISION,
    qty             INTEGER,
    primary_pnl     DOUBLE PRECISION DEFAULT 0,
    pair_pnl        DOUBLE PRECISION DEFAULT 0,
    combined_pnl    DOUBLE PRECISION DEFAULT 0,
    status          TEXT DEFAULT 'open',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at       TIMESTAMPTZ
);

-- Table 4: Transactions — every individual fill event
CREATE TABLE IF NOT EXISTS tg_transactions (
    txn_id          BIGSERIAL PRIMARY KEY,
    cycle_id        INTEGER REFERENCES tg_cycles(cycle_id),
    pair_id         INTEGER NOT NULL REFERENCES tg_pairs(pair_id),
    session_id      INTEGER NOT NULL REFERENCES tg_sessions(session_id),
    ts              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ticker          TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             INTEGER NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    txn_type        TEXT NOT NULL,
    is_partial      BOOLEAN DEFAULT FALSE,
    order_id        TEXT,
    group_id        TEXT,
    pnl_increment   DOUBLE PRECISION DEFAULT 0,
    running_session_pnl DOUBLE PRECISION DEFAULT 0,
    net_inventory   INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'
);

-- Table 5: Inventory — latest position per ticker per session (upserted)
CREATE TABLE IF NOT EXISTS tg_inventory (
    session_id      INTEGER NOT NULL REFERENCES tg_sessions(session_id),
    ticker          TEXT NOT NULL,
    net_qty         INTEGER NOT NULL DEFAULT 0,
    avg_price       DOUBLE PRECISION DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, ticker)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tg_sessions_status ON tg_sessions (status);
CREATE INDEX IF NOT EXISTS idx_tg_sessions_bot ON tg_sessions (bot_type, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_pairs_session ON tg_pairs (session_id);
CREATE INDEX IF NOT EXISTS idx_tg_pairs_ticker ON tg_pairs (primary_ticker);
CREATE INDEX IF NOT EXISTS idx_tg_cycles_pair ON tg_cycles (pair_id);
CREATE INDEX IF NOT EXISTS idx_tg_cycles_session ON tg_cycles (session_id, closed_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_cycles_group ON tg_cycles (group_id);
CREATE INDEX IF NOT EXISTS idx_tg_txn_session ON tg_transactions (session_id, ts);
CREATE INDEX IF NOT EXISTS idx_tg_txn_pair ON tg_transactions (pair_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_tg_txn_ticker ON tg_transactions (ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_tg_txn_type ON tg_transactions (txn_type);
CREATE INDEX IF NOT EXISTS idx_tg_txn_date ON tg_transactions (ts);
CREATE INDEX IF NOT EXISTS idx_tg_txn_group ON tg_transactions (group_id);
