# TG1 — Grid OCO Trading Bot Architecture

## Overview

TG1 is a **two-token grid trading bot with OCO (One-Cancels-Other) hedging** for NSE equity. It trades TokenA on a linear arithmetic grid and hedges with TokenB OCO orders on a correlated instrument. It uses a **multi-account architecture**: 3 separate Findoc XTS sessions for trading (Trade, UpsideOCO, DownsideOCO) and Zerodha KiteTicker WebSocket for real-time market data.

**Reference Implementation:** Ported from [Findoc-Backend GridOcoLogic](../OrderBook/Findoc-Backend/Gridcontroller/GridOcoLogic_ts.js) (Node.js → Python).

**Broker:** Findoc XTS (trading, 3 accounts) + Zerodha (market data via KiteTicker)
**Exchange:** NSE (Cash Market)
**Product:** MIS (intraday) or CNC (delivery)

---

## Table of Contents

1. [Core Concepts](#1-core-concepts)
2. [Two-Token Architecture](#2-two-token-architecture)
3. [Three-Account Model](#3-three-account-model)
4. [Grid Design](#4-grid-design)
5. [Trade Types](#5-trade-types)
6. [Order Lifecycle (State Machine)](#6-order-lifecycle-state-machine)
7. [Entry Order Placement Logic](#7-entry-order-placement-logic)
8. [Entry Fill Handling](#8-entry-fill-handling)
9. [Target Fill Handling](#9-target-fill-handling)
10. [OCO Order Management](#10-oco-order-management)
11. [Dynamic OCO Bracketing](#11-dynamic-oco-bracketing)
12. [Position Tracking](#12-position-tracking)
13. [Termination Conditions](#13-termination-conditions)
14. [Module Architecture](#14-module-architecture)
15. [File Reference](#15-file-reference)
16. [Data Flow](#16-data-flow)
17. [State Persistence](#17-state-persistence)
18. [Startup & Recovery](#18-startup--recovery)
19. [Operational Commands](#19-operational-commands)
20. [Configuration Reference](#20-configuration-reference)
21. [Comparison with TG](#21-comparison-with-tg)

---

## 1. Core Concepts

### The Problem

A grid trading bot places limit orders at regular price intervals above and below a center price. When price oscillates, entries fill and targets capture the spread. However, if price moves strongly in one direction, the bot accumulates a directional position with increasing unrealized loss.

### The Solution: OCO Hedging

TG1 adds a **second token (TokenB)** as a hedge instrument. When a TokenA entry fills, an OCO (One-Cancels-Other) order is placed on TokenB in the opposite economic direction. If the trade goes wrong (price keeps moving against the entry), the OCO order on the correlated instrument limits the loss. If the trade goes right (target fills), the OCO is cancelled.

### Key Terminology

| Term | Meaning |
|------|---------|
| **TokenA** | Grid-traded instrument (entries + targets placed here) |
| **TokenB** | Hedge instrument (OCO orders placed here) |
| **Entry** | Initial limit order on TokenA (BUY below center, SELL above) |
| **Target** | Profit-taking order on TokenA (opposite side of entry) |
| **OCO** | Hedge order on TokenB (placed when entry fills, cancelled when target fills) |
| **Grid Level** | A single price point in the grid that cycles between entry and target states |
| **Upside** | Grid levels above the entry price (SELL entries) |
| **Downside** | Grid levels below the entry price (BUY entries) |
| **Trade Side** | "upside" or "downside" — determines which OCO account is used |

---

## 2. Two-Token Architecture

```
TokenA (Grid-Traded)                    TokenB (OCO Hedge)
━━━━━━━━━━━━━━━━━━━                    ━━━━━━━━━━━━━━━━━━━

  SELL entry @ 52.00 ─────────────────→ BUY OCO @ TokenB + ocoSpread
  SELL entry @ 51.00 ─────────────────→ BUY OCO @ TokenB + ocoSpread

  ────── Entry Price (50.00) ──────     ────── TokenB Price (live) ──────

  BUY entry @ 49.00 ──────────────────→ SELL OCO @ TokenB - ocoSpread
  BUY entry @ 48.00 ──────────────────→ SELL OCO @ TokenB - ocoSpread
```

### How TokenB Price is Captured

TokenB's price is captured **at the moment a TokenA entry fills** (not at bot start or order placement). This ensures the OCO hedge price reflects the actual market conditions when the position was opened.

### OCO Price Calculation

| Entry Direction | OCO Direction | OCO Price Formula |
|----------------|---------------|-------------------|
| BUY (downside) | SELL | `tokenBPrice - ocoSpread` |
| SELL (upside) | BUY | `tokenBPrice + ocoSpread` |

**Important:** The OCO direction matches the target direction (if you BUY TokenA, the OCO is a SELL on TokenB — the same economic direction as your target, providing a hedge if TokenA keeps dropping).

---

## 3. Three-Account Model

TG1 uses **3 separate XTS trading sessions**, each with independent credentials:

```
┌──────────────────────────────────────────────────────┐
│                    TG1 Bot                           │
│                                                      │
│  ┌─────────────────┐  TokenA entries + targets       │
│  │  Trade Account   │  (BUY/SELL on grid levels)     │
│  │  (XTS Session 1) │                                │
│  └─────────────────┘                                │
│                                                      │
│  ┌──────────────────┐  OCO orders for SELL entries   │
│  │ Upside OCO Acct   │  (BUY OCO on TokenB)         │
│  │ (XTS Session 2)   │                               │
│  └──────────────────┘                                │
│                                                      │
│  ┌──────────────────┐  OCO orders for BUY entries    │
│  │ Downside OCO Acct │  (SELL OCO on TokenB)         │
│  │ (XTS Session 3)   │                               │
│  └──────────────────┘                                │
│                                                      │
│  ┌──────────────────┐  Real-time prices              │
│  │ Zerodha KiteTicker│  (TokenA + TokenB LTP)        │
│  │ (WebSocket)       │                               │
│  └──────────────────┘                                │
└──────────────────────────────────────────────────────┘
```

### Why 3 Accounts?

- **Regulatory compliance:** Separate accounts for different trading strategies
- **Risk isolation:** OCO orders can't interfere with grid orders
- **Position tracking:** Each account's position is independently managed

### Same OCO Account Optimization

If `upside_oco_key == downside_oco_key` (same credentials), TG1 detects this and shares a single XTS session for both OCO directions. This affects the termination condition (see [Termination Conditions](#13-termination-conditions)).

---

## 4. Grid Design

TG1 uses a **linear arithmetic grid** — equal spacing between all levels:

```
                          SELL GRID (upside)
                          entries above entry_price

  Level 5  ──── entry_price + 5×spread ────  SELL entry
  Level 4  ──── entry_price + 4×spread ────  SELL entry
  Level 3  ──── entry_price + 3×spread ────  SELL entry
  Level 2  ──── entry_price + 2×spread ────  SELL entry
  Level 1  ──── entry_price + 1×spread ────  SELL entry

            ════════ Entry Price ════════

  Level 1  ──── entry_price - 1×spread ────  BUY entry
  Level 2  ──── entry_price - 2×spread ────  BUY entry
  Level 3  ──── entry_price - 3×spread ────  BUY entry
  Level 4  ──── entry_price - 4×spread ────  BUY entry
  Level 5  ──── entry_price - 5×spread ────  BUY entry

                          BUY GRID (downside)
                          entries below entry_price
```

### Grid Math

For level `i` (1-indexed):
- **SELL entry price:** `entry_price + (i × spread)`
- **SELL target price:** `entry_price + (i × spread) - target_spread`
- **BUY entry price:** `entry_price - (i × spread)`
- **BUY target price:** `entry_price - (i × spread) + target_spread`

### Numerical Example

```
Entry Price = 50.00, Steps = 5, Spread = 1.0, Target Spread = 0.50

SELL Grid (upside):
  Level    Entry     Target
  1        51.00     50.50
  2        52.00     51.50
  3        53.00     52.50
  4        54.00     53.50
  5        55.00     54.50

BUY Grid (downside):
  Level    Entry     Target
  1        49.00     49.50
  2        48.00     48.50
  3        47.00     47.50
  4        46.00     46.50
  5        45.00     45.50
```

### Max Quantity

```
MaxQuantity = token_a_quantity × steps
```

For example, with `qty_a=100` and `steps=5`: `MaxQuantity = 500`.

---

## 5. Trade Types

TG1 supports 5 trade types that control which grid sides are active and whether OCO hedging is used:

| Trade Type | BUY Grid | SELL Grid | OCO | Accounts Needed |
|-----------|----------|-----------|-----|----------------|
| `gridocots` | Yes | Yes | Yes | 3 (Trade + 2 OCO) |
| `buyocots` | Yes | No | Yes | 3 (Trade + 2 OCO) |
| `sellocots` | No | Yes | Yes | 3 (Trade + 2 OCO) |
| `buyts` | Yes | No | No | 1 (Trade only) |
| `sellts` | No | Yes | No | 1 (Trade only) |

### Trade Type Selection Guide

- **`gridocots`** — Full bidirectional grid with OCO. Most capital-efficient but requires 3 accounts.
- **`buyocots`** / **`sellocots`** — Directional bias with OCO protection. Use when you expect a range but lean one way.
- **`buyts`** / **`sellts`** — Simple grid without OCO. Lower complexity, higher directional risk.

---

## 6. Order Lifecycle (State Machine)

Each grid level is represented by an `OpenOrder` record that cycles through states:

```
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  FRESH (order_side='entry', entry_order_id=None)        │
  │  Grid level created, waiting for placement              │
  │                                                         │
  └──────────────────────┬──────────────────────────────────┘
                         │
                  place_entry_orders() picks it up,
                  places LIMIT on exchange
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  ENTRY_PLACED (order_side='entry', entry_order_id='123')│
  │  Waiting for fill...                                    │
  │                                                         │
  └──────────────────────┬──────────────────────────────────┘
                         │
                  Entry fills on exchange
                  Capture TokenB price
                  Compute target + OCO prices
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  TARGET_READY (order_side='target', entry_order_id=None)│
  │  Direction flipped, target price set                    │
  │  OCO trade_price set (if OCO type)                      │
  │                                                         │
  └──────────────────────┬──────────────────────────────────┘
                         │
                  place_entry_orders() picks it up as target,
                  places LIMIT on exchange
                         │
                         ▼
  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │  TARGET_PLACED (order_side='target', entry_order_id='456')
  │  OCO order may be active via dynamic bracketing         │
  │  Waiting for target fill or OCO fill...                 │
  │                                                         │
  └──────────┬─────────────────────────────────┬────────────┘
             │                                 │
      Target fills                      OCO fills
             │                                 │
             ▼                                 ▼
  ┌─────────────────────┐         ┌─────────────────────────┐
  │                     │         │                         │
  │  TARGET_FILLED      │         │  OCO_FILLED             │
  │  • Cancel OCO       │         │  • Cancel target        │
  │  • Reset to FRESH   │         │  • Set oco_filled=True  │
  │  • New UUID         │         │  • Level permanently    │
  │  • Ready for        │         │    closed               │
  │    re-entry         │         │                         │
  │                     │         │                         │
  └─────────────────────┘         └─────────────────────────┘
```

### State Transitions Summary

| From | Event | To | Actions |
|------|-------|----|---------|
| FRESH | Entry placed | ENTRY_PLACED | Store entry_order_id |
| ENTRY_PLACED | Entry fills | TARGET_READY | Capture TokenB price, compute target/OCO prices, flip direction, update counters, record history |
| TARGET_READY | Target placed | TARGET_PLACED | Store entry_order_id (reused field for target) |
| TARGET_PLACED | Target fills | FRESH (new UUID) | Cancel OCO, reset all fields, update counters, clear maxQuantityReached |
| TARGET_PLACED | OCO fills | OCO_FILLED | Cancel target, set oco_filled=True, update counters |
| Any PLACED | Order rejected | Previous state | Clear order_id, retry on next cycle |
| Any PLACED | Order cancelled | Previous state | Clear order_id |

---

## 7. Entry Order Placement Logic

Entry orders are placed **one at a time per side** to control exposure:

### BUY Side Placement

1. Find all BUY entries with `order_side='entry'`, `entry_order_id=None`, `oco_filled=False`
2. Sort **descending** by `entry_trade_price` (nearest to market first)
3. Take only the **first** (limit 1)
4. **MaxQuantity gate:** If the candidate is on `downside` (new entry into market) AND `maxQuantityReached=True`, skip. If on `upside` (target re-entry), always allow.
5. Place LIMIT order

### SELL Side Placement

1. Find all SELL entries with `order_side='entry'`, `entry_order_id=None`, `oco_filled=False`
2. Sort **ascending** by `entry_trade_price` (nearest to market first)
3. Take only the **first** (limit 1)
4. **MaxQuantity gate:** If the candidate is on `upside` (new entry into market) AND `maxQuantityReached=True`, skip. If on `downside` (target re-entry), always allow.
5. Place LIMIT order

### Why One at a Time?

- Prevents over-committing capital to one direction before fills are confirmed
- Ensures the nearest-to-market level is always prioritized
- Reduces exchange order load

---

## 8. Entry Fill Handling

When a TokenA entry fills:

```
Input:
  - Original direction: BUY (example)
  - Entry price: 49.00
  - TokenB current price (from KiteTicker): 120.50

Compute:
  - Target direction: SELL (opposite of BUY)
  - Target price: 49.00 + target_spread = 49.50
  - OCO direction: SELL (same as target — hedge for BUY position)
  - OCO price: 120.50 - oco_spread (e.g., 120.50 - 2.0 = 118.50)

Transform OpenOrder record:
  - entry_order_id = None (clear for target placement)
  - entry_trade_direction = SELL (flipped)
  - entry_trade_price = 49.50 (target price)
  - oco_trade_direction = SELL
  - oco_trade_price = 118.50
  - token_b_price = None (cleared after use)
  - order_side = 'target'

Side effects:
  - Update downside_net_quantity += token_a_quantity (BUY adds to downside)
  - Create OrderHistoryRecord with entry details
```

### Position Counter Updates on Entry Fill

| Entry Direction | Counter Updated |
|----------------|-----------------|
| BUY | `downside_net_quantity += quantity` |
| SELL | `upside_net_quantity += quantity` |

---

## 9. Target Fill Handling

When a TokenA target fills:

```
Input:
  - Current direction: SELL (target of BUY entry)
  - Target price: 49.50
  - Original entry direction: BUY

Actions:
  1. Cancel any active OCO order for this level
  2. Update position counters (reverse the entry)
  3. Update history record with target details
  4. Reset level to entry state:
     - New UUID (uuid4)
     - entry_trade_direction = BUY (back to original)
     - entry_trade_price = 49.00 (back to original entry level)
     - Clear all OCO fields
     - order_side = 'entry'
  5. Clear maxQuantityReached flag (frees up new entry placement)
```

### Position Counter Updates on Target Fill

| Original Entry | Counter Updated |
|---------------|-----------------|
| BUY (target is SELL) | `downside_net_quantity -= quantity` |
| SELL (target is BUY) | `upside_net_quantity -= quantity` |

---

## 10. OCO Order Management

### OCO Fill Handling

When a TokenB OCO order fills:

```
Actions:
  1. Cancel the corresponding target order on TokenA
  2. Mark level as oco_filled = True (permanently closed)
  3. Update OCO net count
  4. Update history record with OCO details
```

### Position Counter Updates on OCO Fill

| Original Entry | Counter Updated |
|---------------|-----------------|
| SELL (OCO is BUY on upside) | `upside_oco_net_count += 1` |
| BUY (OCO is SELL on downside) | `downside_oco_net_count += 1` |

### OCO Account Routing

| Trade Side | OCO Account |
|-----------|-------------|
| `upside` (SELL entries) | Upside OCO Account (Session 2) |
| `downside` (BUY entries) | Downside OCO Account (Session 3) |

---

## 11. Dynamic OCO Bracketing

OCO orders are managed **dynamically** — at most 2 active OCO orders per direction (nearest above + nearest below current TokenB price). This prevents having too many open orders on the exchange.

### Algorithm

For each OCO direction (BUY, SELL):

```
1. Collect all orders with oco_trade_price set (target state, not OCO-filled)

2. Find nearest_below = order with highest oco_trade_price <= current_tokenB_price
   Find nearest_above = order with lowest oco_trade_price > current_tokenB_price

3. These two should have active OCO orders on exchange

4. Cancel all OTHER active OCO orders for this direction
   (they are "stale" — too far from current price)

5. Place OCO orders for nearest_below and nearest_above if not already placed
```

### Visual Example

```
TokenB Price = 120.50

OCO BUY orders (upside, from SELL entries):
  OCO @ 125.00  →  ABOVE ← place this
  OCO @ 123.00  →  ABOVE (not nearest, cancel if active)
  OCO @ 119.00  →  BELOW ← place this
  OCO @ 116.00  →  BELOW (not nearest, cancel if active)
  OCO @ 113.00  →  BELOW (not nearest, cancel if active)

Active OCO orders: max 2 (@ 125.00 and @ 119.00)
```

### Why Dynamic Bracketing?

- Limits exchange order exposure
- Focuses hedging on the most relevant price levels
- Automatically adjusts as TokenB price moves

---

## 12. Position Tracking

TG1 maintains 4 position counters:

| Counter | Updated On | Direction |
|---------|-----------|-----------|
| `upside_net_quantity` | SELL entry fill (+qty), BUY target fill (-qty) | Net SELL exposure |
| `downside_net_quantity` | BUY entry fill (+qty), SELL target fill (-qty) | Net BUY exposure |
| `upside_oco_net_count` | OCO fill on upside level (+1) | Count of upside OCO events |
| `downside_oco_net_count` | OCO fill on downside level (+1) | Count of downside OCO events |

### MaxQuantity Logic

```
if |upside_net_quantity| >= MaxQuantity OR |downside_net_quantity| >= MaxQuantity:
    maxQuantityReached = True
    → PAUSE new entries (targets still allowed)
    → Does NOT terminate the bot
    → Reset when any target fills
```

**Important:** MaxQuantity is a **global** flag. It pauses ALL new entries regardless of which side reached the limit.

---

## 13. Termination Conditions

TG1 auto-terminates under two conditions:

### Condition 1: OCO Imbalance

The bot terminates if too many OCO orders have filled on one side (indicating strong directional movement that the grid cannot handle).

**Same OCO Account:**
```python
terminate = abs(upside_oco_net_count - downside_oco_net_count) >= steps
```

**Different OCO Accounts:**
```python
terminate = abs(upside_oco_net_count) >= steps OR abs(downside_oco_net_count) >= steps
```

### Condition 2: Untriggered OCO Buildup

OCO orders that should have already been filled (based on TokenB price) but haven't. This indicates the OCO orders are failing to execute (broker issue, insufficient margin, etc.).

```python
# BUY OCO orders at or below current TokenB price should have filled
untriggered_buy = count(oco where direction='BUY' AND oco_price <= tokenB_price)

# SELL OCO orders at or above current TokenB price should have filled
untriggered_sell = count(oco where direction='SELL' AND oco_price >= tokenB_price)

terminate = untriggered_buy >= oco_stop_count OR untriggered_sell >= oco_stop_count
```

### Termination Action

When either condition triggers:
1. Cancel ALL active orders (entries, targets, OCOs) across all 3 accounts
2. Set bot_status to "Terminated: {reason}"
3. Save state
4. Exit polling loop

---

## 14. Module Architecture

```
TG1/
├── __init__.py          # Package init
├── config.py            # GridOcoConfig dataclass
├── models.py            # OpenOrder, OrderHistoryRecord dataclasses
├── state.py             # StateManager (JSON persistence)
├── findoc_client.py     # FindocMultiClient (3 XTS sessions + Zerodha)
├── zerodha_feed.py      # ZerodhaFeed (KiteTicker WebSocket)
├── grid_engine.py       # GridOcoEngine (main orchestrator)
├── run.py               # CLI entry point
├── requirements.txt     # Python dependencies
├── ARCHITECTURE.md      # This document
├── state/               # Runtime state files (auto-created)
│   └── {bot_name}_state.json
└── logs/                # Log files (auto-created)
    └── grid_oco_engine.log
```

### Dependency Graph

```
run.py
  └─→ grid_engine.py (GridOcoEngine)
        ├─→ config.py (GridOcoConfig)
        ├─→ models.py (OpenOrder, OrderHistoryRecord)
        ├─→ state.py (StateManager)
        ├─→ findoc_client.py (FindocMultiClient)
        │     ├─→ TG/sdk/Connect.py (XTSConnect) × 3 sessions
        │     └─→ kiteconnect (KiteConnect) — instrument cache
        └─→ zerodha_feed.py (ZerodhaFeed)
              └─→ kiteconnect (KiteTicker) — WebSocket prices
```

---

## 15. File Reference

### `config.py` — Configuration

| Class | Purpose |
|-------|---------|
| `GridOcoConfig` | All bot parameters: grid, OCO, credentials, operational settings |

Key features:
- `validate()` — Comprehensive validation of all parameters
- `print_grid_layout()` — Prints full grid with entry/target prices
- `has_oco` property — Whether this trade type uses OCO orders
- `max_quantity` property — `token_a_quantity × steps`
- `same_oco_account` property — Whether upside/downside OCO share credentials

### `models.py` — Data Models

| Class | Purpose |
|-------|---------|
| `OpenOrder` | Grid level record that cycles between entry and target states |
| `OrderHistoryRecord` | Completed trade record stored in history |

OpenOrder key fields:
- `uuid` — Unique identifier (regenerated on target fill for re-entry)
- `entry_order_id` — XTS order ID (None when not placed, reused for target)
- `oco_order_id` — XTS OCO order ID
- `entry_trade_direction` — Current direction (BUY/SELL, flips on fill)
- `entry_trade_price` — Current price (changes from entry to target)
- `oco_trade_price` — Computed OCO hedge price
- `token_b_price` — Captured TokenB price at entry placement
- `order_side` — 'entry' or 'target'
- `oco_filled` — True = permanently closed level

### `state.py` — State Persistence

| Class | Purpose |
|-------|---------|
| `StateManager` | Atomic JSON persistence, position counters, order search |

Key methods:
- `save()` — Atomic write (write to .tmp, then os.replace)
- `load()` — Restore state from JSON
- `update_quantity(order_type, side, qty)` — Update position counters
- `find_order_by_uuid/entry_id/oco_id()` — Search helpers

### `findoc_client.py` — Multi-Account Client

| Class | Purpose |
|-------|---------|
| `_XTSSession` | Single XTS Interactive session wrapper |
| `FindocMultiClient` | 3 XTS sessions + Zerodha KiteConnect |

Session roles:
- `trade_session` — TokenA entries + targets
- `upside_oco_session` — OCO orders for SELL entries
- `downside_oco_session` — OCO orders for BUY entries

Key features:
- Instrument cache: `exchange_token` (for XTS orders) + `instrument_token` (for KiteTicker)
- `round_to_tick(price, symbol)` — Rounds to valid tick size
- `_get_oco_session(trade_side)` — Routes to correct OCO session

### `zerodha_feed.py` — Real-Time Prices

| Class | Purpose |
|-------|---------|
| `ZerodhaFeed` | KiteTicker WebSocket in daemon thread, thread-safe LTP dict |

Key features:
- Runs in background daemon thread
- Thread-safe price dict with lock
- Auto-reconnect on disconnect
- MODE_LTP for minimal data

### `grid_engine.py` — Core Engine

| Class | Purpose |
|-------|---------|
| `GridOcoEngine` | Main orchestrator: grid creation, polling, fill handling, OCO management |

Key methods:
- `start()` — Connect → create/load grid → start feed → polling loop
- `_create_grid_levels()` — Create initial OpenOrder records
- `_place_entry_orders()` — One-at-a-time per side (BUY DESC, SELL ASC)
- `_handle_entry_fill()` — Transform to target state, compute OCO
- `_handle_target_fill()` — Reset to entry state, new UUID
- `_handle_oco_fill()` — Mark permanently closed
- `_manage_oco_orders()` — Dynamic bracketing
- `_check_termination()` — OCO imbalance + untriggered buildup
- `cancel_all()` — Cancel all orders across all sessions

### `run.py` — CLI Entry Point

Full argparse CLI with all parameters. Supports:
- `--dry-run` — Print grid layout without trading
- `--auto-entry` — Use current LTP as entry price
- `--cancel-all` — Cancel all open orders and exit

---

## 16. Data Flow

### Main Polling Loop (1-second interval)

```
_poll_cycle()
    │
    ├─→ _check_termination()       # OCO imbalance? Untriggered buildup?
    │     └─→ terminate + cancel_all if triggered
    │
    ├─→ _check_max_quantity()      # Pause entries if maxQty reached
    │
    ├─→ _place_entry_orders()      # Place 1 BUY + 1 SELL (nearest to market)
    │     ├─→ BUY: sorted DESC, limit 1, maxQty gate
    │     └─→ SELL: sorted ASC, limit 1, maxQty gate
    │
    ├─→ _poll_entry_orders()       # Check placed entries for fills
    │     └─→ COMPLETE: _handle_entry_fill()
    │           ├─→ Capture TokenB price
    │           ├─→ Compute target + OCO prices
    │           ├─→ Transform record to target state
    │           └─→ Update position counters + history
    │
    ├─→ _poll_target_orders()      # Check placed targets for fills
    │     └─→ COMPLETE: _handle_target_fill()
    │           ├─→ Cancel OCO order
    │           ├─→ Reset level to entry state (new UUID)
    │           ├─→ Update position counters + history
    │           └─→ Clear maxQuantityReached
    │
    ├─→ _poll_oco_orders()         # Check placed OCOs for fills
    │     └─→ COMPLETE: _handle_oco_fill()
    │           ├─→ Cancel target order
    │           ├─→ Mark level oco_filled=True
    │           └─→ Update position counters + history
    │
    └─→ _manage_oco_orders()       # Dynamic OCO bracketing
          ├─→ For BUY OCOs: find nearest above/below TokenB price
          ├─→ For SELL OCOs: find nearest above/below TokenB price
          ├─→ Cancel stale OCOs (not nearest)
          └─→ Place needed OCOs (nearest but not placed)
```

### Complete Trade Lifecycle Example

```
1. Bot starts with entry_price=50.00, spread=1.0, target_spread=0.50

2. Grid created:
   BUY @ 49.00 (downside, level 1)
   BUY @ 48.00 (downside, level 2)
   SELL @ 51.00 (upside, level 1)
   SELL @ 52.00 (upside, level 2)

3. BUY @ 49.00 placed (nearest to market, DESC sort picks highest)

4. Price drops to 49.00, BUY fills
   → TokenB price captured: 120.50
   → Target: SELL @ 49.50 (49.00 + 0.50)
   → OCO: SELL @ 118.50 (120.50 - 2.00)
   → downside_net_quantity += 100

5. SELL target @ 49.50 placed on TokenA (Trade account)
   → OCO SELL @ 118.50 placed on TokenB (Downside OCO account)
     (if nearest to current TokenB price per dynamic bracketing)

6a. SCENARIO A — Target fills:
    → SELL @ 49.50 fills, cancel OCO @ 118.50
    → downside_net_quantity -= 100 (back to 0)
    → Level reset: new UUID, BUY @ 49.00 ready for re-entry
    → maxQuantityReached = False

6b. SCENARIO B — OCO fills:
    → SELL OCO @ 118.50 fills on TokenB
    → Cancel target SELL @ 49.50 on TokenA
    → downside_oco_net_count += 1
    → Level marked oco_filled=True (permanently closed)
```

---

## 17. State Persistence

State is persisted to `TG1/state/{bot_name}_state.json` using atomic writes.

### State File Structure

```json
{
  "bot_name": "IRFC-SBIN Grid",
  "bot_status": "Active",
  "trade_type": "gridocots",
  "token_a_symbol": "IRFC",
  "token_b_symbol": "SBIN",
  "entry_price": 50.00,
  "max_quantity": 500,
  "upside_net_quantity": 100.0,
  "downside_net_quantity": 200.0,
  "upside_oco_net_count": 0,
  "downside_oco_net_count": 1,
  "total_pnl": 0.0,
  "last_updated": "2026-02-16T10:30:00",
  "open_orders": [
    {
      "uuid": "a1b2c3d4e5f6",
      "bot_name": "IRFC-SBIN Grid",
      "entry_order_id": "12345",
      "oco_order_id": null,
      "entry_trade_direction": "BUY",
      "entry_trade_price": 49.00,
      "oco_trade_price": null,
      "trade_side": "downside",
      "oco_filled": false,
      "order_side": "entry",
      "token_a_quantity": 100,
      "token_b_quantity": 50
    }
  ],
  "order_history": [...]
}
```

### Persistence Rules

- State saved after every fill or OCO management change
- Order history trimmed to last 500 entries
- Atomic write: write to `.tmp`, then `os.replace()` — prevents corruption on crash
- On startup, state is loaded and reconciled with broker order book

---

## 18. Startup & Recovery

### Fresh Start

```
1. connect()                → 3 XTS logins + Zerodha instrument cache
2. Start KiteTicker         → WebSocket for TokenA + TokenB prices
3. Wait for initial prices  → Up to 30 seconds timeout
4. _create_grid_levels()    → Create OpenOrder records for all levels
5. state.save()             → Persist initial state
6. _run_loop()              → Enter 1-second polling loop
```

### Resume After Restart

```
1. connect()                → 3 XTS logins + Zerodha instrument cache
2. Start KiteTicker         → WebSocket for TokenA + TokenB prices
3. state.load()             → Restore open orders + counters
4. _reconcile_orders()      → Check actual order statuses:
   - Process missed entry fills
   - Process missed target fills
   - Process missed OCO fills
   - Clear cancelled/rejected order IDs
5. state.save()             → Persist reconciled state
6. _run_loop()              → Enter 1-second polling loop
```

---

## 19. Operational Commands

### Start Bidirectional Grid with OCO

```bash
python -m TG1.run --bot-name "IRFC-SBIN Grid" \
    --trade-type gridocots \
    --token-a IRFC --token-b SBIN \
    --entry-price 50.00 --steps 5 --spread 1.0 \
    --target-spread 0.50 --oco-spread 2.0 \
    --qty-a 100 --qty-b 50 \
    --trade-key KEY --trade-secret SECRET \
    --upside-oco-key KEY2 --upside-oco-secret SECRET2 \
    --downside-oco-key KEY3 --downside-oco-secret SECRET3
```

### Start Buy-Only Grid (No OCO)

```bash
python -m TG1.run --bot-name "IRFC Buy Grid" \
    --trade-type buyts \
    --token-a IRFC --entry-price 50.00 \
    --steps 5 --spread 0.50 --target-spread 0.25 \
    --qty-a 100 \
    --trade-key KEY --trade-secret SECRET
```

### Auto-Entry (Use Current LTP)

```bash
python -m TG1.run --bot-name "IRFC Grid" \
    --trade-type buyts --auto-entry \
    --token-a IRFC --steps 5 --spread 0.50 \
    --target-spread 0.25 --qty-a 100 \
    --trade-key KEY --trade-secret SECRET
```

### Dry Run (Print Grid Only)

```bash
python -m TG1.run --bot-name "Test" \
    --trade-type gridocots \
    --token-a IRFC --token-b SBIN \
    --entry-price 50.00 --steps 5 --spread 1.0 \
    --target-spread 0.50 --oco-spread 2.0 \
    --qty-a 100 --qty-b 50 --dry-run
```

### Cancel All Open Orders

```bash
python -m TG1.run --bot-name "IRFC-SBIN Grid" --cancel-all \
    --token-a IRFC \
    --trade-key KEY --trade-secret SECRET \
    --upside-oco-key KEY2 --upside-oco-secret SECRET2 \
    --downside-oco-key KEY3 --downside-oco-secret SECRET3
```

---

## 20. Configuration Reference

### GridOcoConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bot_name` | str | (required) | Unique bot identifier |
| `trade_type` | str | gridocots | One of: gridocots, buyocots, sellocots, buyts, sellts |
| `token_a_symbol` | str | (required) | Grid-traded instrument (NSE symbol) |
| `token_b_symbol` | str | "" | OCO hedge instrument (required for OCO types) |
| `entry_price` | float | 0.0 | Grid center price |
| `steps` | int | 5 | Number of grid levels per side |
| `spread` | float | 1.0 | Spacing between grid levels |
| `target_spread` | float | 1.0 | Target offset from entry price |
| `oco_spread` | float | 0.0 | OCO offset from TokenB price |
| `token_a_quantity` | int | 0 | Quantity per grid level (TokenA) |
| `token_b_quantity` | int | 0 | Quantity per OCO order (TokenB) |
| `product_type` | str | MIS | MIS (intraday) or NRML/CNC |
| `exchange` | str | NSE | Exchange |
| `oco_stop_count` | int | 3 | Untriggered OCO threshold for termination |
| `trade_key` | str | "" | XTS API key for Trade account |
| `trade_secret` | str | "" | XTS API secret for Trade account |
| `upside_oco_key` | str | "" | XTS API key for Upside OCO account |
| `upside_oco_secret` | str | "" | XTS API secret for Upside OCO account |
| `downside_oco_key` | str | "" | XTS API key for Downside OCO account |
| `downside_oco_secret` | str | "" | XTS API secret for Downside OCO account |
| `zerodha_user` | str | Sai | Zerodha user for market data |
| `xts_root` | str | xts.myfindoc.com | XTS API root URL |
| `poll_interval` | float | 1.0 | Polling interval in seconds |
| `auto_reenter` | bool | True | Re-enter after target fill |

### Logging

Logs are written to both stdout and `TG1/logs/grid_oco_engine.log`.

Key log patterns:
```
[downside] ENTRY BUY placed: IRFC 100 @ 49.00 -> ID=12345
[downside] ENTRY FILLED: BUY IRFC @ 49.00 (filled 49.00) | Target: SELL @ 49.50 | OCO: SELL @ 118.50 | TokenB: 120.50
[downside] TARGET FILLED: SELL @ 49.50 (filled 49.50)
[downside] Level reset for re-entry: BUY @ 49.00
[upside] OCO FILLED: BUY @ 125.00 (filled 124.95)
MAX QUANTITY REACHED — pausing new entries
TERMINATING: OCO imbalance — upside_oco=5 downside_oco=0 steps=5
```

---

## 21. Comparison with TG

| Feature | TG | TG1 |
|---------|-----|------|
| **Grid type** | Geometric (spacing doubles each level) | Linear (equal spacing) |
| **Instruments** | Single token | Two tokens (TokenA grid + TokenB OCO) |
| **Accounts** | 1 XTS session | 3 XTS sessions |
| **OCO hedging** | No | Yes (dynamic bracketing) |
| **Price feed** | Order polling only (no live prices) | KiteTicker WebSocket (live LTP) |
| **Order placement** | All levels at once | One at a time per side |
| **Trade types** | Buy + Sell (always both) | 5 types (with/without OCO, uni/bi-directional) |
| **Termination** | Manual only | Auto (OCO imbalance + untriggered buildup) |
| **Max quantity** | No concept | Pauses entries (does not terminate) |
| **Target convergence** | All targets converge to single price | Targets at fixed offset from each entry |
| **Re-entry** | Same level, same group | New UUID, fresh record |
| **Reference impl** | Custom design | Ported from Findoc-Backend GridOcoLogic |
