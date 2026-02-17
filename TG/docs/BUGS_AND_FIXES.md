# TG Grid Bot — Bugs & Fixes

Catalog of bugs found and resolved during development of the TG grid trading system (Feb 2026).

---

## Bug #1: Order ID exceeds 20-char XTS limit

| | |
|---|---|
| **Severity** | Critical |
| **File** | `TG/config.py` |
| **Discovered** | During first order placement attempt |

**Symptom:** Every order placement returned a rejection from XTS. The `orderUniqueIdentifier` field was being rejected silently — orders never appeared in the order book.

**Root Cause:** The original order ID format included both primary and secondary symbol names:
```
TATSILV-SPCENET-A-L0-abc12345   (31 chars)
```
XTS enforces a strict **20-character maximum** on `orderUniqueIdentifier`. Any excess characters caused the order to be rejected at the API level.

**Fix:** Redesigned `generate_order_id()` to use a compact format that omits symbol names (XTS order record already contains the symbol):
```python
# Format: {ROLE}[{SEQ}]-{BOT}-L{LEVEL}-{GROUP_ID}
# Examples:
#   EN-A-L0-abc12345     (16 chars)
#   TP-B-L5-abc12345     (16 chars)
#   PH1-A-L0-abc12345    (17 chars)
#   PU1-B-L99-abc12345   (19 chars, extreme)
def generate_order_id(primary, secondary, subset_index,
                      role, bot, group_id, seq=0):
    tag = role
    if seq > 0:
        tag += str(seq)
    return f"{tag}-{bot}-L{subset_index}-{group_id}"
```

---

## Bug #2: SPCENET SELL orders not filling (illiquid bid-ask)

| | |
|---|---|
| **Severity** | High |
| **File** | `TG/hybrid_client.py` |
| **Discovered** | First pair hedge attempt on SPCENET |

**Symptom:** SPCENET pair hedge SELL orders were placed at the last traded price (LTP) but never filled. The order would sit in OPEN status indefinitely.

**Root Cause:** SPCENET is an illiquid stock with a wide bid-ask spread. A SELL order placed exactly at LTP sits between bid and ask — it doesn't hit the bid, so nobody takes it. XTS doesn't support native MARKET orders for equity, so we use aggressive LIMIT orders.

**Fix:** Implemented `place_market_order()` with configurable slippage. SELL orders are priced at `LTP - slippage` to hit the bid, BUY orders at `LTP + slippage` to hit the ask:
```python
def place_market_order(self, symbol, transaction_type, qty,
                       exchange="NSE", product="NRML",
                       order_unique_id="", slippage=0.02):
    ltp = self.get_ltp(symbol, exchange)
    if transaction_type == "SELL":
        price = round(ltp - slippage, 2)
    else:
        price = round(ltp + slippage, 2)
    return self.place_order(symbol, transaction_type, qty, price, ...)
```

---

## Bug #3: Duplicate orders on restart (no status guard)

| | |
|---|---|
| **Severity** | High |
| **File** | `TG/engine.py` |
| **Discovered** | After first bot restart with saved state |

**Symptom:** When the bot restarted with existing state, it re-processed COMPLETE fills from the order book, leading to duplicate target orders and double pair hedges.

**Root Cause:** The `_handle_fill_event()` method did not check if the group had already transitioned past the relevant status. A COMPLETE entry fill for a group already in `TARGET_PENDING` status would be processed again.

**Fix:** Added status guards at the top of both entry and target fill handlers:
```python
def _handle_fill_event(self, order):
    ...
    # Entry order
    if order_id == group.entry_order_id:
        if group.status != GroupStatus.ENTRY_PENDING:
            logger.debug("Skipping entry fill for group=%s "
                         "(status=%s, already processed)",
                         group.group_id, group.status)
            return False
        ...

    # Target order
    elif order_id == group.target_order_id:
        if group.status != GroupStatus.TARGET_PENDING:
            logger.debug("Skipping target fill for group=%s "
                         "(status=%s, already processed)",
                         group.group_id, group.status)
            return False
        ...
```

---

## Bug #4: Order book parse crash (empty string fields)

| | |
|---|---|
| **Severity** | Medium |
| **File** | `TG/hybrid_client.py` |
| **Discovered** | During live order book polling |

**Symptom:** `get_orders()` would crash with `ValueError: invalid literal for int()` when parsing the XTS order book. The entire poll cycle would fail, causing the bot to miss fill events.

**Root Cause:** XTS returns empty strings (`""`) for numeric fields like `CumulativeQuantity`, `OrderQuantity`, and `OrderAverageTradedPrice` on orders that haven't been processed yet. Direct `int()` or `float()` conversion fails on empty strings.

**Fix:** Added `or 0` fallback for all numeric fields in the order normalization:
```python
normalized.append({
    'order_id': str(o.get('AppOrderID', '')),
    'status': _STATUS_MAP.get(xts_status, xts_status),
    'average_price': float(o.get('OrderAverageTradedPrice', 0) or 0),
    'filled_quantity': int(o.get('CumulativeQuantity', 0) or 0),
    'quantity': int(o.get('OrderQuantity', 0) or 0),
    ...
})
```
The `or 0` pattern handles both `None` and `""` cases.

---

## Bug #5: apiOrderSource rejection (empty string)

| | |
|---|---|
| **Severity** | Medium |
| **File** | `TG/hybrid_client.py` |
| **Discovered** | During order placement testing |

**Symptom:** Orders were rejected by XTS with a vague error about invalid parameters. No specific field was identified in the error response.

**Root Cause:** The `apiOrderSource` parameter was being passed as an empty string. XTS requires this to be a non-empty string identifying the source application.

**Fix:** Hardcoded `apiOrderSource="WebAPI"` in the `place_order()` method:
```python
resp = self.xt.place_order(
    ...
    orderUniqueIdentifier=order_unique_id or "",
    apiOrderSource="WebAPI",
)
```

---

## Bug #6: SELL + NRML RMS block (NONSQROFF)

| | |
|---|---|
| **Severity** | High |
| **File** | `TG/bot_sell.py` |
| **Discovered** | First SellBot entry order on live account |

**Symptom:** All SELL LIMIT NRML orders were rejected by XTS RMS with error code `NONSQROFF` — "Selling not allowed without holdings."

**Root Cause:** For `NRML` (carry-forward) SELL orders on equity, XTS/Findoc RMS requires the account to hold the shares. Unlike MIS (intraday), NRML SELLs are treated as delivery sells and require pre-existing holdings. The bot had no holdings on the Findoc account.

**Fix:** Two-part solution:
1. **Holdings check in SellBot**: Before placing sell entries, check available qty via API (or use `holdings_override` config):
```python
def place_entries(self):
    if self.config.holdings_override >= 0:
        available = self.config.holdings_override
    else:
        available = self.client.get_available_qty(self.config.symbol)

    for level in self.levels:
        if available < level.qty:
            logger.warning("Insufficient holdings for subset=%d", ...)
            continue
        ...
```
2. **Seed purchases**: Bought shares on the Findoc account (TATSILV, TATAGOLD, SPCENET, IDEA) to satisfy RMS requirements.

---

## Bug #7: Multi-bot session conflict

| | |
|---|---|
| **Severity** | Critical |
| **File** | `TG/hybrid_client.py` |
| **Discovered** | When launching second primary bot (TATAGOLD) alongside TATSILV |

**Symptom:** When the second bot logged in to XTS, the first bot's session was invalidated. All subsequent API calls from the first bot failed with authentication errors.

**Root Cause:** XTS Interactive allows only ONE active session per API key. Each `interactive_login()` call generates a new token and invalidates the previous one. Multiple bot processes each doing their own login caused a "last login wins" race condition.

**Fix:** Implemented shared session file (`TG/state/.xts_session.json`). The first process to start does a fresh login and saves the token; subsequent processes reuse it:
```python
_SESSION_FILE = os.path.join(_SESSION_DIR, '.xts_session.json')
_SESSION_MAX_AGE = 8 * 3600  # 8 hours

def connect(self):
    if self._try_reuse_session():
        logger.info("XTS session reused from file")
    else:
        resp = self.xt.interactive_login()
        self._save_session(resp['result']['token'], ...)

def _try_reuse_session(self):
    # Load from file, check age < 8h, validate with get_order_book()
    ...

def _save_session(self, token, user_id):
    # Atomic write: tmp file + os.replace()
    ...
```

---

## Bug #8: Partial fills not hedged

| | |
|---|---|
| **Severity** | High |
| **File** | `TG/engine.py`, `TG/config.py` |
| **Discovered** | Observing SPCENET hedge gaps during live trading |

**Symptom:** When an entry order was partially filled (e.g., 200 of 300 shares), no pair hedge was placed until the order was fully COMPLETE. This left the position unhedged during the partial fill period.

**Root Cause:** The original `_handle_fill_event()` only hedged on `COMPLETE` status. Partial fills were detected for cache invalidation but triggered no hedge action.

**Fix:** Added dual hedge ratio system — `hedge_ratio` for COMPLETE fills, `partial_hedge_ratio` for PARTIAL fills:
```python
# config.py
hedge_ratio: int = 0            # on COMPLETE (0 = disabled)
partial_hedge_ratio: int = 0    # on PARTIAL (0 = disabled)

# engine.py — entry fill handler
increment = filled_qty - group.entry_filled_so_far
if is_complete:
    target_hedge = filled_qty * self.config.hedge_ratio
    remaining = target_hedge - group.pair_hedged_qty
    if remaining > 0:
        bot.place_pair_hedge(group, remaining)
else:
    if self.config.partial_hedge_ratio > 0:
        pair_qty = increment * self.config.partial_hedge_ratio
        bot.place_pair_hedge(group, pair_qty)
```
The COMPLETE handler accounts for shares already hedged during PARTIAL fills, preventing double-hedging.

---

## Bug #9: Partial fill PnL calculation wrong

| | |
|---|---|
| **Severity** | Medium |
| **File** | `TG/group.py` |
| **Discovered** | Reviewing pair PnL numbers after first trading session |

**Symptom:** Pair PnL displayed inconsistent numbers — sometimes showing massive gains or losses that didn't match actual trade prices.

**Root Cause:** The original pair PnL calculation used single-price tracking (`pair_hedge_price`, `pair_unwind_price`), but with multiple partial hedge/unwind orders at different prices, the single price was overwritten each time. The calculation `(unwind_price - hedge_price) * total_qty` was wrong when multiple fills occurred at different prices.

**Fix:** Switched to cumulative VWAP-based tracking on the Group dataclass:
```python
# Cumulative totals (sum of price * qty for each fill)
pair_hedge_total: float = 0.0     # sum(hedge_price * hedge_qty)
pair_hedged_qty: int = 0          # total shares hedged
pair_unwind_total: float = 0.0    # sum(unwind_price * unwind_qty)
pair_unwound_qty: int = 0         # total shares unwound

# PnL computed from totals, not single prices
pair_pnl = round(pair_unwind_total - pair_hedge_total, 2)

# VWAP properties for display
@property
def pair_hedge_vwap(self):
    return round(self.pair_hedge_total / self.pair_hedged_qty, 2) \
           if self.pair_hedged_qty else 0.0
```

---

## Bug #10: Pair trading activity not visible

| | |
|---|---|
| **Severity** | Low |
| **File** | `TG/group.py`, `TG/dashboard.py` |
| **Discovered** | Trying to monitor SPCENET hedge activity via dashboard |

**Symptom:** The monitor dashboard showed primary grid activity but had zero visibility into what SPCENET (secondary) orders were being placed. No way to see hedge/unwind prices, timing, or net SPCENET position.

**Root Cause:** Pair orders were fire-and-forget — placed and logged, but not tracked in state. The dashboard had no data source to display secondary activity.

**Fix:** Two-part solution:
1. **Group-level pair order log** (`TG/group.py`): Added `pair_orders: List[Dict]` field that records every hedge/unwind order:
```python
pair_orders: List[Dict] = field(default_factory=list)
# Each entry: {xts_id, custom_id, side, qty, price, role, ts}
```

2. **SPCENET dashboard tab** (`TG/dashboard.py`): Added a dedicated tab on the 7777 monitor that aggregates all pair orders across all primaries:
   - KPIs: Total Pair Orders, Net Qty, Pair PnL
   - Table: Time, Primary, Bot, Level, Role (HEDGE/UNWIND), Side, Qty, Price, XTS Order ID, Custom ID, Group

---

## Summary

| # | Bug | Severity | Status |
|---|-----|----------|--------|
| 1 | Order ID exceeds 20-char XTS limit | Critical | Fixed |
| 2 | SPCENET SELL orders not filling | High | Fixed |
| 3 | Duplicate orders on restart | High | Fixed |
| 4 | Order book parse crash (empty fields) | Medium | Fixed |
| 5 | apiOrderSource rejection | Medium | Fixed |
| 6 | SELL+NRML RMS block | High | Fixed |
| 7 | Multi-bot session conflict | Critical | Fixed |
| 8 | Partial fills not hedged | High | Fixed |
| 9 | Partial fill PnL wrong | Medium | Fixed |
| 10 | Pair activity not visible | Low | Fixed |
