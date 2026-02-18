"""
TollGate — Single-ticker market-making bot for SPCENET.

Runs on a separate XTS account ("Interactive Order Data") and performs
simple grid market-making: symmetric buy/sell grids around a reference
price, collecting 0.01 round-trip profit per completed cycle.

Fully self-contained on XTS — no Zerodha dependency. Uses XTS Interactive
for trading and XTS Market Data WebSocket for real-time LTP/bid/ask.

Components:
    client.py    — TollGateClient (XTS Interactive + Market Data WebSocket)
    config.py    — TollGateConfig dataclass + grid level computation
    state.py     — TollGateState + TollGateGroup (JSON persistence)
    engine.py    — TollGateEngine (unified polling loop, fill handling, reanchor)
    dashboard.py — Flask dashboards: Monitor (:7788) + Config (:7786)
    warmup.py    — Morning warmup script (kill/login/cancel/reset/start/verify)
    run.py       — CLI entry point
"""
