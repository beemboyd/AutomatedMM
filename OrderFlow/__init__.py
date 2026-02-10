"""
OrderFlow Module - Real-time order flow analysis for Indian equity markets.

Captures L1/L2 tick data via Zerodha KiteTicker WebSocket, stores in TimescaleDB,
and computes order flow metrics (delta, CVD, imbalance, absorption, phase detection)
to identify Wyckoff-style market phases: accumulation, markup, distribution, markdown.
"""
