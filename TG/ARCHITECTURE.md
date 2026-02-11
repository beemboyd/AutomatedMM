# TG — Grid Trading Bot Architecture

## Overview

TG is a symmetric grid trading bot for NSE equity, operating two bots (Buy Bot A and Sell Bot B) on a single broker account via the XTS (Symphony Fintech / Findoc) API. It places LIMIT orders at geometrically-spaced levels around an anchor price, capturing the bid-ask spread through continuous entry-target cycles.

**Ticker:** SPCENET
**Broker:** XTS / Findoc (Symphony Fintech)
**Exchange:** NSE (Cash Market)
**Product:** NRML (carry-forward, equivalent to CNC)
**Session:** Orders persist overnight — shutdown does NOT cancel orders

---

## Table of Contents

1. [Grid Design](#1-grid-design)
2. [Position Sizing](#2-position-sizing)
3. [Convergence Property](#3-convergence-property)
4. [Module Architecture](#4-module-architecture)
5. [File Reference](#5-file-reference)
6. [Data Flow](#6-data-flow)
7. [Group Lifecycle](#7-group-lifecycle)
8. [State Persistence](#8-state-persistence)
9. [XTS Integration](#9-xts-integration)
10. [Startup & Recovery](#10-startup--recovery)
11. [Operational Commands](#11-operational-commands)
12. [Risk & Constraints](#12-risk--constraints)
13. [Configuration Reference](#13-configuration-reference)

---

## 1. Grid Design

The grid is symmetric around an **anchor price** (P0). Buy Bot A places entries below P0, Sell Bot B places entries above P0.

Each grid level uses **geometric doubling** — spacing and target offset double with each successive subset:

```
        SELL GRID (Bot B)                          BUY GRID (Bot A)
        entries above anchor                       entries below anchor

  S3  ──── P0 + 0.15 ────                   ──── P0 - 0.15 ──── S3
            ↕ 0.08                                     ↕ 0.08
  S2  ──── P0 + 0.07 ────                   ──── P0 - 0.07 ──── S2
            ↕ 0.04                                     ↕ 0.04
  S1  ──── P0 + 0.03 ────                   ──── P0 - 0.03 ──── S1
            ↕ 0.02                                     ↕ 0.02
  S0  ──── P0 + 0.01 ────                   ──── P0 - 0.01 ──── S0
                          ─── P0 (anchor) ───
```

### Grid Math

For subset `i`:
- `grid_space(i) = base_grid_space × 2^i`
- `target(i) = base_target × 2^i`
- `distance(i) = Σ grid_space(0..i)` (cumulative)

With defaults `base_grid_space=0.01`, `base_target=0.02`:

| Subset | Grid Space | Target | Cumulative Distance | Qty |
|--------|-----------|--------|-------------------|-----|
| 0 | 0.01 | 0.02 | 0.01 | 300 |
| 1 | 0.02 | 0.04 | 0.03 | 300 |
| 2 | 0.04 | 0.08 | 0.07 | 300 |
| 3 | 0.08 | 0.16 | 0.15 | 100 |

### Entry & Target Prices

**Buy Bot A** (entries below anchor):
```
entry(i)  = P0 - distance(i)
target(i) = entry(i) + target(i) = P0 - distance(i) + base_target × 2^i
```

**Sell Bot B** (entries above anchor):
```
entry(i)  = P0 + distance(i)
target(i) = entry(i) - target(i) = P0 + distance(i) - base_target × 2^i
```

### Numerical Example (P0 = 50.00)

**Buy Grid:**
| Subset | Entry | Target | Spread |
|--------|-------|--------|--------|
| 0 | 49.99 | 50.01 | 0.02 |
| 1 | 49.97 | 50.01 | 0.04 |
| 2 | 49.93 | 50.01 | 0.08 |
| 3 | 49.85 | 50.01 | 0.16 |

**Sell Grid:**
| Subset | Entry | Target | Spread |
|--------|-------|--------|--------|
| 0 | 50.01 | 49.99 | 0.02 |
| 1 | 50.03 | 49.99 | 0.04 |
| 2 | 50.07 | 49.99 | 0.08 |
| 3 | 50.15 | 49.99 | 0.16 |

---

## 2. Position Sizing

Total position: **1000 shares**, split into subsets of **300 shares** each.

```
Subset 0: 300 shares  (nearest to anchor)
Subset 1: 300 shares
Subset 2: 300 shares
Subset 3: 100 shares  (remainder, deepest level)
Total:   1000 shares
```

The allocation formula:
- Each subset gets `min(subset_qty, remaining)` shares
- Subsets are generated until `remaining = 0`
- Deeper subsets have wider spacing, reducing adverse selection risk at deeper fills

---

## 3. Convergence Property

**Critical design feature:** All buy targets converge to a single price, and all sell targets converge to a single price.

```
All buy targets  → P0 + base_grid_space  (e.g., 50.01)
All sell targets → P0 - base_grid_space  (e.g., 49.99)
```

**Proof:**

For buy subset `i`:
```
target(i) = entry(i) + target_offset(i)
          = (P0 - Σ(j=0..i) space(j)) + base_target × 2^i
          = P0 - (space(0) + space(1) + ... + space(i)) + base_target × 2^i
```

Since `space(j) = base_grid_space × 2^j`:
```
Σ(j=0..i) space(j) = base_grid_space × (2^(i+1) - 1)
```

And `target_offset(i) = base_target × 2^i = 2 × base_grid_space × 2^i = base_grid_space × 2^(i+1)`:
```
target(i) = P0 - base_grid_space × (2^(i+1) - 1) + base_grid_space × 2^(i+1)
          = P0 + base_grid_space
```

**Effective spread = 2 × base_grid_space = 2 paisa**

This means no matter which subset fills, the target always converges to the same price, simplifying order management and ensuring consistent profitability per cycle.

---

## 4. Module Architecture

```
TG/
├── __init__.py          # Package init
├── config.py            # GridConfig, SubsetConfig dataclasses
├── grid.py              # GridCalculator, GridLevel
├── group.py             # Group lifecycle model, GroupStatus
├── state.py             # StateManager (JSON persistence)
├── xts_client.py        # XTS API wrapper (trading + market data)
├── bot_buy.py           # Buy Bot A
├── bot_sell.py           # Sell Bot B
├── engine.py            # GridEngine orchestrator
├── run.py               # CLI entry point
├── sdk/                 # XTS Python SDK (cloned + patched)
│   ├── Connect.py       # XTSConnect class (patched for path/import)
│   ├── config.ini       # SDK configuration
│   └── Exception.py     # SDK exception classes
├── state/               # Runtime state files (auto-created)
│   └── {SYMBOL}_grid_state.json
├── logs/                # Log files (auto-created)
│   └── grid_engine.log
└── ARCHITECTURE.md      # This document
```

### Dependency Graph

```
run.py
  └─→ engine.py (GridEngine)
        ├─→ config.py (GridConfig)
        ├─→ grid.py (GridCalculator)
        ├─→ state.py (StateManager)
        ├─→ xts_client.py (XTSClient)
        │     └─→ sdk/Connect.py (XTSConnect)
        ├─→ bot_buy.py (BuyBot)
        │     ├─→ grid.py (GridLevel)
        │     ├─→ group.py (Group, GroupStatus)
        │     ├─→ state.py (StateManager)
        │     ├─→ xts_client.py (XTSClient)
        │     └─→ config.py (GridConfig)
        └─→ bot_sell.py (SellBot)
              ├─→ grid.py (GridLevel)
              ├─→ group.py (Group, GroupStatus)
              ├─→ state.py (StateManager)
              ├─→ xts_client.py (XTSClient)
              └─→ config.py (GridConfig)
```

---

## 5. File Reference

### `config.py` — Configuration

| Class | Purpose |
|-------|---------|
| `SubsetConfig` | Per-subset params: index, qty, grid_space, target, distance_from_anchor |
| `GridConfig` | Main config: symbol, anchor, grid params, XTS credentials, operational settings |

Key methods:
- `compute_subsets()` — Generates subset list with geometric doubling
- `from_args()` — Factory from CLI arguments, validates credentials
- `print_grid_layout()` — Prints full grid for visual verification

### `grid.py` — Grid Calculator

| Class | Purpose |
|-------|---------|
| `GridLevel` | Single level: subset_index, side, entry_price, target_price, qty |
| `GridCalculator` | Computes buy/sell levels from config subsets |

Key methods:
- `compute_buy_levels()` — Entry prices below anchor
- `compute_sell_levels()` — Entry prices above anchor

### `group.py` — Trade Group Model

| Class | Purpose |
|-------|---------|
| `GroupStatus` | Enum-like: ENTRY_PENDING, ENTRY_FILLED, TARGET_PENDING, CLOSED, CANCELLED |
| `Group` | Dataclass tracking entry+target order pair with fills, timestamps, PnL |

Key methods:
- `Group.create()` — Factory with UUID-based group_id
- `to_dict()` / `from_dict()` — JSON serialization for state persistence

### `state.py` — State Manager

| Class | Purpose |
|-------|---------|
| `StateManager` | JSON persistence for open/closed groups, order mapping, cumulative PnL |

Key methods:
- `add_group()` — Register new group + entry order mapping
- `register_order()` — Map target order ID to group
- `close_group()` — Move to closed, accumulate PnL, increment cycle count
- `get_group_by_order()` — Look up group by any order ID (entry or target)
- `save()` / `load()` — Atomic JSON persistence via tmp + os.replace
- `get_open_groups_for_bot()` — Filter open groups by bot ID

### `xts_client.py` — XTS API Wrapper

| Class | Purpose |
|-------|---------|
| `XTSClient` | Wraps XTS SDK with same interface as original Zerodha client |

Two internal XTSConnect instances:
- `self.xt` — Interactive (trading): order placement, cancellation, order book
- `self.xt_md` — Market Data: LTP quotes, instrument search

Key methods:
- `connect()` — Dual login (interactive + market data)
- `resolve_instrument()` — Symbol → exchangeInstrumentID (cached)
- `place_order()` — LIMIT order with product/segment mapping
- `cancel_order()` — Cancel by AppOrderID
- `get_orders()` — Normalized order book (status mapping to engine format)
- `get_ltp()` — Last traded price via touchline quote
- `get_available_qty()` — Holdings check for sell bot

### `bot_buy.py` — Buy Bot A

| Class | Purpose |
|-------|---------|
| `BuyBot` | Manages buy entries below anchor and sell targets |

Key methods:
- `place_entries()` — Place BUY LIMIT at all free levels
- `on_entry_fill()` — Handle fill → place SELL LIMIT target
- `on_target_fill()` — Handle target fill → close group, compute PnL, re-enter
- `cancel_all()` — Cancel all active orders for this bot

### `bot_sell.py` — Sell Bot B

| Class | Purpose |
|-------|---------|
| `SellBot` | Manages sell entries above anchor and buy targets |

Key methods:
- `place_entries()` — Place SELL LIMIT at free levels (checks holdings first)
- `on_entry_fill()` — Handle fill → place BUY LIMIT target
- `on_target_fill()` — Handle target fill → close group, compute PnL, re-enter
- `cancel_all()` — Cancel all active orders for this bot

**CNC constraint:** SellBot checks `get_available_qty()` before placing sell entries. If insufficient holdings, the level is skipped.

### `engine.py` — Grid Engine

| Class | Purpose |
|-------|---------|
| `GridEngine` | Main orchestrator: init, polling, fill routing, shutdown |

Key methods:
- `start()` — Connect → load/init state → place entries → poll loop
- `_run_loop()` — Main polling loop with configurable interval
- `_poll_orders()` — Fetch order book, detect status changes, route fills
- `_handle_fill()` — Route fill to correct bot (A/B) and type (entry/target)
- `_handle_rejection()` — Log and free level on entry rejection
- `_reconcile_orders()` — On startup, process any fills that occurred while offline
- `cancel_all()` — Cancel all orders across both bots
- `_shutdown()` — Save state, log summary (orders remain active)

### `run.py` — CLI Entry Point

CLI arguments:
- `--symbol` — NSE symbol (required)
- `--anchor` / `--auto-anchor` — Grid center price
- `--grid-space` — Base spacing (default: 0.01)
- `--target` — Base target (default: 0.02)
- `--total-qty` — Total shares (default: 1000)
- `--subset-qty` — Per-subset shares (default: 300)
- `--product` — NRML or MIS (default: NRML)
- `--dry-run` — Print grid, no orders
- `--cancel-all` — Cancel all open orders and exit
- `--no-reenter` — Disable auto re-entry after target fill

---

## 6. Data Flow

### Order Placement Flow

```
GridEngine.start()
    │
    ├─→ XTSClient.connect()          # dual login
    ├─→ StateManager.load()          # load or init state
    │
    ├─→ BuyBot.place_entries()       # for each free level:
    │     ├─→ Group.create()         #   create group (ENTRY_PENDING)
    │     ├─→ XTSClient.place_order()#   place BUY LIMIT
    │     ├─→ StateManager.add_group()#  register group + order mapping
    │     └─→ level_groups[i] = gid  #   mark level as active
    │
    └─→ SellBot.place_entries()      # same as above with holdings check
          ├─→ XTSClient.get_available_qty()  # check holdings first
          └─→ ... (same flow as BuyBot)
```

### Poll & Fill Routing Flow

```
GridEngine._run_loop()
    │
    └─→ _poll_orders() [every poll_interval seconds]
          │
          ├─→ XTSClient.get_orders()         # fetch normalized order book
          │
          └─→ for each order with status change:
                │
                ├─→ status == COMPLETE:
                │     └─→ _handle_fill(order)
                │           │
                │           ├─→ StateManager.get_group_by_order()
                │           │
                │           ├─→ if entry fill:
                │           │     ├─→ BuyBot.on_entry_fill()    # → place SELL target
                │           │     └─→ SellBot.on_entry_fill()   # → place BUY target
                │           │
                │           └─→ if target fill:
                │                 ├─→ BuyBot.on_target_fill()   # → close, PnL, re-enter
                │                 └─→ SellBot.on_target_fill()  # → close, PnL, re-enter
                │
                ├─→ status == REJECTED:
                │     └─→ _handle_rejection()   # free level, remove group
                │
                └─→ status == CANCELLED:
                      └─→ _handle_cancellation() # log only
```

### PnL Calculation

**Buy Bot A** (buy low, sell high):
```
PnL = (target_fill_price - entry_fill_price) × fill_qty
```

**Sell Bot B** (sell high, buy low):
```
PnL = (entry_fill_price - target_fill_price) × fill_qty
```

---

## 7. Group Lifecycle

Each trade is tracked as a **Group** (entry order + target order pair):

```
                                  ┌──────────────┐
                                  │ Group.create()│
                                  └──────┬───────┘
                                         │
                                         ▼
                              ┌──────────────────┐
                    ┌─────────│  ENTRY_PENDING    │─────────┐
                    │         │  (entry order     │         │
                    │         │   placed)         │         │
                    │         └──────────────────┘         │
                    │                    │                   │
               REJECTED            COMPLETE            CANCELLED
                    │                    │                   │
                    ▼                    ▼                   ▼
             ┌──────────┐    ┌──────────────────┐   ┌──────────┐
             │ Level     │    │  ENTRY_FILLED    │   │ Level    │
             │ freed,    │    │  (place target   │   │ freed    │
             │ group     │    │   order)         │   └──────────┘
             │ removed   │    └──────────────────┘
             └──────────┘              │
                                       ▼
                              ┌──────────────────┐
                              │  TARGET_PENDING   │
                              │  (target order    │
                              │   placed)         │
                              └──────────────────┘
                                       │
                                  COMPLETE
                                       │
                                       ▼
                              ┌──────────────────┐
                              │     CLOSED        │
                              │  PnL realized,    │
                              │  level freed,     │
                              │  re-enter if      │
                              │  configured       │
                              └──────────────────┘
```

---

## 8. State Persistence

State is persisted to `TG/state/{SYMBOL}_grid_state.json` using atomic writes (write to `.tmp`, then `os.replace`).

### State File Structure

```json
{
  "symbol": "SPCENET",
  "anchor_price": 50.00,
  "total_pnl": 12.50,
  "total_cycles": 85,
  "last_updated": "2026-02-11T15:30:00",
  "open_groups": {
    "a1b2c3d4": {
      "group_id": "a1b2c3d4",
      "bot": "A",
      "subset_index": 0,
      "entry_side": "BUY",
      "entry_price": 49.99,
      "target_price": 50.01,
      "qty": 300,
      "status": "TARGET_PENDING",
      "entry_order_id": "12345",
      "target_order_id": "12346",
      "entry_fill_price": 49.99,
      "entry_fill_qty": 300,
      "realized_pnl": 0.0,
      "created_at": "2026-02-11T09:15:00",
      "entry_filled_at": "2026-02-11T09:15:02"
    }
  },
  "closed_groups": [ ... ],
  "order_to_group": {
    "12345": "a1b2c3d4",
    "12346": "a1b2c3d4"
  }
}
```

### Persistence Rules

- State is saved after every fill event
- Closed groups are trimmed to the last 500 (200 in the file) for audit trail
- On shutdown, state is saved but orders are NOT cancelled (NRML persists)
- On startup, state is loaded and reconciled with the broker order book

---

## 9. XTS Integration

### Dual-Instance Architecture

XTS requires two separate API sessions because `interactive_login()` and `marketdata_login()` overwrite the same internal `self.token` field:

```
XTSClient
  ├── self.xt      (XTSConnect)  ← interactive_login()  → trading
  └── self.xt_md   (XTSConnect)  ← marketdata_login()   → quotes
```

### XTS vs Zerodha Mapping

| Concept | Zerodha | XTS |
|---------|---------|-----|
| Product (carry-forward) | CNC | NRML |
| Product (intraday) | MIS | MIS |
| Order ID field | order_id | AppOrderID |
| Instrument ID | tradingsymbol (string) | exchangeInstrumentID (numeric) |
| Exchange segment | NSE | NSECM |
| Fill status | COMPLETE | Filled |
| Pending status | OPEN | New / Open |

### Order Status Normalization

XTS statuses are normalized to engine-expected format:

| XTS Status | Normalized |
|-----------|-----------|
| New | OPEN |
| PendingNew | OPEN |
| Open | OPEN |
| Replaced | OPEN |
| PartiallyFilled | PARTIAL |
| Filled | COMPLETE |
| Cancelled | CANCELLED |
| PendingCancel | CANCELLED |
| Rejected | REJECTED |

### Instrument Resolution

Symbols (e.g., "SPCENET") must be resolved to numeric `exchangeInstrumentID`:

1. Try `search_by_scriptname()` — search by name, match exact symbol + exchange
2. Fallback: `get_equity_symbol()` — search by series (EQ) + symbol
3. Result is cached in `_instrument_cache` for the session

### XTS SDK Patches

The SDK (`TG/sdk/Connect.py`) was patched to fix:

1. **config.ini path** — Changed from `cfg.read('config.ini')` (reads from CWD) to `cfg.read(os.path.join(_sdk_dir, 'config.ini'))` with fallback defaults
2. **Exception import** — Added `sys.path.insert(0, _sdk_dir)` so `import Exception as ex` resolves correctly when SDK is imported as a subpackage

---

## 10. Startup & Recovery

### Fresh Start

```
1. connect()              → dual XTS login
2. print_grid_layout()    → visual verification
3. state.load()           → returns False (no state file)
4. buy_bot.place_entries() → place all 4 BUY LIMIT entries
5. sell_bot.place_entries()→ place SELL LIMIT entries (holdings permitting)
6. state.save()           → persist initial state
7. _run_loop()            → enter polling loop
```

### Resume After Shutdown

```
1. connect()              → dual XTS login
2. state.load()           → returns True, restores open groups
3. restore_level_groups() → rebuild level → group mappings for both bots
4. _reconcile_orders()    → check broker for fills that occurred while offline
5. place_entries()        → place entries only for FREE levels
6. state.save()           → persist reconciled state
7. _run_loop()            → enter polling loop
```

### Reconciliation Logic

On startup with existing state, the engine:
- Fetches the full order book from the broker
- For each open group with ENTRY_PENDING: checks if the entry order was filled, cancelled, or rejected while offline
- For each open group with TARGET_PENDING: checks if the target order was filled
- Processes any missed fills through the normal fill handling pipeline
- Frees levels for cancelled/rejected entries

---

## 11. Operational Commands

### Start Grid Bot
```bash
python -m TG.run --symbol SPCENET --anchor 50.25
```

### Auto-Anchor (use current LTP)
```bash
python -m TG.run --symbol SPCENET --auto-anchor
```

### Dry Run (print grid, no orders)
```bash
python -m TG.run --symbol SPCENET --anchor 50.25 --dry-run
```

### Cancel All Orders
```bash
python -m TG.run --symbol SPCENET --anchor 50.25 --cancel-all
```

### Custom Grid Parameters
```bash
python -m TG.run --symbol SPCENET --anchor 50.25 \
    --grid-space 0.05 --target 0.10 \
    --total-qty 1000 --subset-qty 300
```

### Custom Credentials
```bash
python -m TG.run --symbol SPCENET --anchor 50.25 \
    --interactive-key YOUR_KEY --interactive-secret YOUR_SECRET \
    --marketdata-key YOUR_MD_KEY --marketdata-secret YOUR_MD_SECRET \
    --xts-root https://your-api-endpoint.com
```

### Disable Auto Re-Entry
```bash
python -m TG.run --symbol SPCENET --anchor 50.25 --no-reenter
```

---

## 12. Risk & Constraints

### Position Limits
- Maximum buy exposure: `total_qty` shares at deepest buy level
- Maximum sell exposure: `total_qty` shares at deepest sell level (constrained by holdings)
- Effective spread captured per cycle: `2 × base_grid_space`

### Sell Bot Holdings Constraint
- SellBot checks `get_available_qty()` before placing each sell entry
- Accounts for qty already committed in pending sell entries
- Levels are skipped (not failed) when holdings are insufficient
- Re-entry also checks holdings before placing new sell entries

### Order Persistence
- NRML orders survive overnight — engine shutdown does NOT cancel orders
- Use `--cancel-all` to explicitly cancel all open orders
- State file tracks all active orders for reconciliation on restart

### Failure Handling
- Rejected entries: level is freed, group is removed from state
- Failed order placement: logged as ERROR, level remains free for retry on next cycle
- Poll loop errors: caught, logged, and retried after `2 × poll_interval`
- State is saved after every fill event to minimize data loss
- Atomic writes prevent state corruption on crash

### Graceful Shutdown
- SIGINT (Ctrl+C) and SIGTERM trigger graceful shutdown
- State is saved, summary is printed
- Orders remain active on the exchange
- Bot can be restarted and will resume from saved state

---

## 13. Configuration Reference

### GridConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `symbol` | str | (required) | NSE trading symbol |
| `anchor_price` | float | (required) | Grid center price |
| `base_grid_space` | float | 0.01 | Base spacing in INR (1 paisa) |
| `base_target` | float | 0.02 | Base target offset in INR (2 paisa) |
| `total_qty` | int | 1000 | Total position size |
| `subset_qty` | int | 300 | Shares per grid subset |
| `exchange` | str | NSE | Exchange |
| `product` | str | NRML | Product type (NRML or MIS) |
| `auto_reenter` | bool | True | Re-place entry after target fills |
| `poll_interval` | float | 2.0 | Seconds between order polls |
| `interactive_key` | str | "" | XTS Interactive API key |
| `interactive_secret` | str | "" | XTS Interactive API secret |
| `marketdata_key` | str | "" | XTS Market Data API key |
| `marketdata_secret` | str | "" | XTS Market Data API secret |
| `xts_root` | str | (symphony URL) | XTS API root URL |

### Logging

Logs are written to both stdout and `TG/logs/grid_engine.log`.

Log levels: DEBUG, INFO, WARNING, ERROR (configurable via `--log-level`).

Key log patterns:
```
BuyBot ENTRY: subset=0, BUY 300 @ 49.99, group=a1b2c3d4, order=12345
BuyBot ENTRY FILLED: group=a1b2c3d4, BUY 300 @ 49.99
BuyBot TARGET: group=a1b2c3d4, SELL 300 @ 50.01, order=12346
BuyBot TARGET FILLED: group=a1b2c3d4, SELL 300 @ 50.01, PnL=6.00
Group a1b2c3d4 closed. PnL=6.00, Total PnL=12.00, Cycles=2
```
