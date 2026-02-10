-- OrderFlow PostgreSQL Schema
-- Uses the existing tick_data database (shared with Simplified_India_TS)
-- Plain PostgreSQL tables with proper indexes for time-series queries

-- Table 1: of_raw_ticks
-- Every FULL-mode tick as received from KiteTicker
CREATE TABLE IF NOT EXISTS of_raw_ticks (
    ts                    TIMESTAMPTZ NOT NULL,
    instrument_token      INTEGER NOT NULL,
    symbol                TEXT NOT NULL,
    last_price            DOUBLE PRECISION NOT NULL,
    last_traded_quantity  INTEGER NOT NULL,
    average_traded_price  DOUBLE PRECISION,
    volume_traded         BIGINT,
    total_buy_quantity    BIGINT,
    total_sell_quantity   BIGINT,
    oi                    BIGINT DEFAULT 0,
    ohlc_open             DOUBLE PRECISION,
    ohlc_high             DOUBLE PRECISION,
    ohlc_low              DOUBLE PRECISION,
    ohlc_close            DOUBLE PRECISION,
    last_trade_time       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_of_raw_ticks_symbol_ts ON of_raw_ticks (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_of_raw_ticks_ts ON of_raw_ticks (ts DESC);

-- Table 2: of_depth_snapshots
-- 5-level bid/ask depth stored as JSONB
CREATE TABLE IF NOT EXISTS of_depth_snapshots (
    ts                  TIMESTAMPTZ NOT NULL,
    instrument_token    INTEGER NOT NULL,
    symbol              TEXT NOT NULL,
    buy_depth           JSONB NOT NULL,
    sell_depth          JSONB NOT NULL,
    bid_ask_spread      DOUBLE PRECISION,
    total_bid_qty       BIGINT,
    total_ask_qty       BIGINT,
    bid_ask_imbalance   DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_of_depth_symbol_ts ON of_depth_snapshots (symbol, ts DESC);

-- Table 3: of_metrics
-- Computed metrics every N seconds
CREATE TABLE IF NOT EXISTS of_metrics (
    ts                      TIMESTAMPTZ NOT NULL,
    symbol                  TEXT NOT NULL,
    interval_seconds        INTEGER DEFAULT 10,
    -- Delta
    trade_delta             DOUBLE PRECISION,
    cumulative_delta        DOUBLE PRECISION,
    delta_divergence        BOOLEAN DEFAULT FALSE,
    -- Phase detection
    phase                   TEXT DEFAULT 'unknown',
    phase_confidence        DOUBLE PRECISION DEFAULT 0,
    -- Imbalance
    bid_ask_imbalance_l1    DOUBLE PRECISION,
    bid_ask_imbalance_l5    DOUBLE PRECISION,
    stacked_imbalance_buy   INTEGER DEFAULT 0,
    stacked_imbalance_sell  INTEGER DEFAULT 0,
    -- Volume
    interval_volume         BIGINT,
    interval_buy_volume     BIGINT,
    interval_sell_volume    BIGINT,
    vwap                    DOUBLE PRECISION,
    -- Large trades
    large_trade_count       INTEGER DEFAULT 0,
    large_trade_volume      BIGINT DEFAULT 0,
    -- Absorption
    absorption_buy          BOOLEAN DEFAULT FALSE,
    absorption_sell         BOOLEAN DEFAULT FALSE,
    -- Price
    price_open              DOUBLE PRECISION,
    price_high              DOUBLE PRECISION,
    price_low               DOUBLE PRECISION,
    price_close             DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_of_metrics_symbol_ts ON of_metrics (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_of_metrics_ts ON of_metrics (ts DESC);

-- Materialized view: 1-minute bars from of_metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS of_metrics_1min AS
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
    (array_agg(price_close ORDER BY ts DESC))[1] AS close
FROM of_metrics
GROUP BY bucket, symbol;

CREATE UNIQUE INDEX IF NOT EXISTS idx_of_metrics_1min_pk ON of_metrics_1min (bucket, symbol);
