-- OrderFlow TimescaleDB Schema
-- Creates hypertables for raw ticks, depth snapshots, and computed metrics

-- Table 1: raw_ticks (hypertable, 1-day chunks)
-- Every FULL-mode tick as received from KiteTicker
CREATE TABLE IF NOT EXISTS raw_ticks (
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

SELECT create_hypertable('raw_ticks', 'ts', chunk_time_interval => INTERVAL '1 day',
                          if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_raw_ticks_symbol_ts ON raw_ticks (symbol, ts DESC);

-- Table 2: depth_snapshots (hypertable, 1-day chunks)
-- 5-level bid/ask depth stored as JSONB
CREATE TABLE IF NOT EXISTS depth_snapshots (
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

SELECT create_hypertable('depth_snapshots', 'ts', chunk_time_interval => INTERVAL '1 day',
                          if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_depth_symbol_ts ON depth_snapshots (symbol, ts DESC);

-- Table 3: orderflow_metrics (hypertable, 1-day chunks)
-- Computed metrics every N seconds
CREATE TABLE IF NOT EXISTS orderflow_metrics (
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

SELECT create_hypertable('orderflow_metrics', 'ts', chunk_time_interval => INTERVAL '1 day',
                          if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_metrics_symbol_ts ON orderflow_metrics (symbol, ts DESC);

-- Continuous Aggregate: 1-minute bars from orderflow_metrics
CREATE MATERIALIZED VIEW IF NOT EXISTS orderflow_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', ts) AS bucket,
    symbol,
    SUM(trade_delta) AS delta_1m,
    LAST(cumulative_delta, ts) AS cvd,
    AVG(bid_ask_imbalance_l5) AS avg_imbalance,
    SUM(interval_volume) AS volume_1m,
    SUM(large_trade_count) AS large_trades,
    LAST(phase, ts) AS phase,
    FIRST(price_open, ts) AS open,
    MAX(price_high) AS high,
    MIN(price_low) AS low,
    LAST(price_close, ts) AS close
FROM orderflow_metrics
GROUP BY bucket, symbol;

-- Retention policies
SELECT add_retention_policy('raw_ticks', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('depth_snapshots', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('orderflow_metrics', INTERVAL '90 days', if_not_exists => TRUE);

-- Enable compression on older chunks
ALTER TABLE raw_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'ts DESC'
);
SELECT add_compression_policy('raw_ticks', INTERVAL '2 days', if_not_exists => TRUE);

ALTER TABLE depth_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'ts DESC'
);
SELECT add_compression_policy('depth_snapshots', INTERVAL '2 days', if_not_exists => TRUE);

ALTER TABLE orderflow_metrics SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'ts DESC'
);
SELECT add_compression_policy('orderflow_metrics', INTERVAL '7 days', if_not_exists => TRUE);
