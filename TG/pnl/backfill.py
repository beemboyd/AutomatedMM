"""
Backfill PnL database from existing JSON state files.

Reads TG Grid Bot and TollGate state files, creates sessions, pairs,
cycles, and transactions in PostgreSQL for historical visibility.

Usage:
    python -m TG.pnl.backfill          # dry-run (prints what would be inserted)
    python -m TG.pnl.backfill --apply  # actually insert into DB
"""

import json
import logging
import os
import sys
import argparse
from datetime import datetime

import psycopg2.extras

# Ensure parent dir is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from TG.pnl.db_manager import PnLDBManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# TG Grid state files
TG_STATE_DIR = os.path.join(BASE_DIR, 'state')
TG_CONFIG_PATH = os.path.join(TG_STATE_DIR, 'tg_config.json')

# TollGate state files
TOLLGATE_STATE_DIR = os.path.join(BASE_DIR, 'TollGate', 'state')


def parse_ts(ts_str):
    """Parse ISO timestamp string to datetime, or return None."""
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None


def load_json(path):
    """Load JSON file, return None on error."""
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load %s: %s", path, e)
        return None


def backfill_tg_grid(db, config, state_data, symbol, dry_run=True):
    """Backfill one TG Grid Bot symbol."""
    secondary = config.get('secondary_symbol', 'SPCENET')
    anchor = state_data.get('anchor_price', 0)
    spacing = state_data.get('current_buy_spacing', 0.01)
    total_pnl = state_data.get('total_pnl', 0)
    total_cycles = state_data.get('total_cycles', 0)

    # Find primary config
    primary_cfg = None
    for p in config.get('primaries', []):
        if p['symbol'] == symbol:
            primary_cfg = p
            break

    levels = primary_cfg.get('levels_per_side', 10) if primary_cfg else 10
    qty = primary_cfg.get('qty_per_level', 100) if primary_cfg else 100
    product = primary_cfg.get('product', 'NRML') if primary_cfg else 'NRML'

    logger.info("=== TG Grid: %s-%s (pnl=%.2f, cycles=%d) ===",
                symbol, secondary, total_pnl, total_cycles)

    closed_groups = state_data.get('closed_groups', [])
    open_groups = state_data.get('open_groups', {})

    logger.info("  Closed groups: %d, Open groups: %d",
                len(closed_groups), len(open_groups))

    if dry_run:
        logger.info("  [DRY RUN] Would create session, pair, %d closed cycles, %d open cycles",
                    len(closed_groups), len(open_groups))
        return

    # Create session
    session_id = db.create_session('tg_grid', {
        'symbol': symbol,
        'secondary': secondary,
        'anchor_price': anchor,
        'spacing': spacing,
        'source': 'backfill'
    })

    # Create pair
    pair_id = db.create_pair(
        session_id=session_id,
        primary_ticker=symbol,
        secondary_ticker=secondary,
        pair_type='hedged',
        anchor_price=anchor,
        grid_spacing=spacing,
        levels_per_side=levels,
        qty_per_level=qty,
        product=product
    )

    running_pnl = 0.0

    # Import closed groups as completed cycles
    for g in closed_groups:
        group_id = g['group_id']
        bot_id = g.get('bot', 'A')
        grid_level = g.get('subset_index', 0)
        entry_side = g.get('entry_side', 'BUY')
        entry_price = g.get('entry_price', 0)
        target_price = g.get('target_price', 0)
        g_qty = g.get('qty', qty)
        entry_fill = g.get('entry_fill_price', entry_price)
        target_fill = g.get('target_fill_price', target_price)
        realized_pnl = g.get('realized_pnl', 0)
        pair_pnl = g.get('pair_pnl', 0)

        # Open cycle
        cycle_id = db.open_cycle(
            pair_id=pair_id, session_id=session_id,
            group_id=group_id, bot_id=bot_id,
            grid_level=grid_level, cycle_number=1,
            entry_side=entry_side, entry_price=entry_price,
            target_price=target_price, qty=g_qty
        )

        # Set opened_at from state timestamp
        created_at = parse_ts(g.get('created_at'))
        if created_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tg_cycles SET opened_at = %s WHERE cycle_id = %s",
                               (created_at, cycle_id))

        # Record ENTRY transaction
        entry_filled_at = parse_ts(g.get('entry_filled_at'))
        db.record_transaction(
            cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
            ticker=symbol, side=entry_side, qty=g_qty,
            price=entry_fill or entry_price,
            txn_type='ENTRY', order_id=g.get('entry_order_id'),
            group_id=group_id
        )
        # Set entry transaction timestamp
        if entry_filled_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tg_transactions SET ts = %s WHERE cycle_id = %s AND txn_type = 'ENTRY'",
                    (entry_filled_at, cycle_id))

        # Record TARGET transaction
        target_side = 'SELL' if entry_side == 'BUY' else 'BUY'
        primary_pnl = realized_pnl - pair_pnl  # realized includes pair, split them
        running_pnl += realized_pnl
        db.record_transaction(
            cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
            ticker=symbol, side=target_side, qty=g_qty,
            price=target_fill or target_price,
            txn_type='TARGET', order_id=g.get('target_order_id'),
            group_id=group_id, pnl_increment=realized_pnl,
            running_session_pnl=running_pnl
        )
        target_filled_at = parse_ts(g.get('target_filled_at'))
        if target_filled_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE tg_transactions SET ts = %s WHERE cycle_id = %s AND txn_type = 'TARGET'",
                    (target_filled_at, cycle_id))

        # Record PAIR_HEDGE and PAIR_UNWIND from pair_orders
        for po in g.get('pair_orders', []):
            role = po.get('role', '')
            po_ts = parse_ts(po.get('ts'))
            if role == 'HEDGE':
                txn_type = 'PAIR_HEDGE'
            elif role == 'UNWIND':
                txn_type = 'PAIR_UNWIND'
            else:
                continue

            txn_id = db.record_transaction(
                cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
                ticker=secondary, side=po.get('side', 'BUY'),
                qty=po.get('qty', g_qty), price=po.get('price', 0),
                txn_type=txn_type, order_id=po.get('xts_id'),
                group_id=group_id
            )
            if po_ts:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE tg_transactions SET ts = %s WHERE txn_id = %s",
                        (po_ts, txn_id))

        # Close the cycle
        primary_pnl_val = (target_fill - entry_fill) * g_qty if entry_side == 'BUY' else (entry_fill - target_fill) * g_qty
        db.close_cycle(
            cycle_id=cycle_id,
            entry_fill_price=entry_fill or 0,
            target_fill_price=target_fill or 0,
            primary_pnl=primary_pnl_val,
            pair_pnl=pair_pnl
        )
        # Set closed_at timestamp
        closed_at = parse_ts(g.get('closed_at'))
        if closed_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tg_cycles SET closed_at = %s WHERE cycle_id = %s",
                               (closed_at, cycle_id))

        # Upsert inventory (net zero for closed cycles)
        db.upsert_inventory(session_id, symbol, 0, 0)

    # Import open groups
    for gid, g in open_groups.items():
        group_id = g['group_id']
        bot_id = g.get('bot', 'A')
        grid_level = g.get('subset_index', 0)
        entry_side = g.get('entry_side', 'BUY')
        entry_price = g.get('entry_price', 0)
        target_price = g.get('target_price', 0)
        g_qty = g.get('qty', qty)
        status = g.get('status', 'ENTRY_PENDING')

        cycle_id = db.open_cycle(
            pair_id=pair_id, session_id=session_id,
            group_id=group_id, bot_id=bot_id,
            grid_level=grid_level, cycle_number=1,
            entry_side=entry_side, entry_price=entry_price,
            target_price=target_price, qty=g_qty
        )

        created_at = parse_ts(g.get('created_at'))
        if created_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tg_cycles SET opened_at = %s WHERE cycle_id = %s",
                               (created_at, cycle_id))

        # If entry is filled, record ENTRY transaction
        entry_fill = g.get('entry_fill_price')
        if entry_fill and g.get('entry_filled_so_far', 0) > 0:
            db.record_transaction(
                cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
                ticker=symbol, side=entry_side,
                qty=g.get('entry_filled_so_far', g_qty),
                price=entry_fill, txn_type='ENTRY',
                order_id=g.get('entry_order_id'), group_id=group_id
            )
            entry_filled_at = parse_ts(g.get('entry_filled_at'))
            if entry_filled_at:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE tg_transactions SET ts = %s WHERE cycle_id = %s AND txn_type = 'ENTRY'",
                        (entry_filled_at, cycle_id))

            # Record pair hedge orders if any
            for po in g.get('pair_orders', []):
                role = po.get('role', '')
                po_ts = parse_ts(po.get('ts'))
                txn_type = 'PAIR_HEDGE' if role == 'HEDGE' else 'PAIR_UNWIND' if role == 'UNWIND' else None
                if not txn_type:
                    continue
                txn_id = db.record_transaction(
                    cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
                    ticker=secondary, side=po.get('side', 'BUY'),
                    qty=po.get('qty', g_qty), price=po.get('price', 0),
                    txn_type=txn_type, order_id=po.get('xts_id'),
                    group_id=group_id
                )
                if po_ts:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE tg_transactions SET ts = %s WHERE txn_id = %s",
                            (po_ts, txn_id))

    # Update pair PnL
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tg_pairs SET pair_pnl = %s, pair_cycles = %s WHERE pair_id = %s",
            (total_pnl, total_cycles, pair_id))

    # Update session totals (keep active since bots are running)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tg_sessions SET total_pnl = %s, total_cycles = %s WHERE session_id = %s",
            (total_pnl, total_cycles, session_id))

    logger.info("  Backfilled %s: session=%d, pair=%d, %d closed + %d open cycles",
                symbol, session_id, pair_id, len(closed_groups), len(open_groups))

    return session_id, pair_id


def backfill_tollgate(db, state_data, dry_run=True):
    """Backfill TollGate state."""
    symbol = state_data.get('symbol', 'SPCENET')
    anchor = state_data.get('anchor_price', 0)
    spacing = state_data.get('current_spacing', 0.01)
    total_pnl = state_data.get('total_pnl', 0)
    total_cycles = state_data.get('total_cycles', 0)
    net_inventory = state_data.get('net_inventory', 0)

    closed_groups = state_data.get('closed_groups', [])
    open_groups = state_data.get('open_groups', {})

    logger.info("=== TollGate: %s (pnl=%.2f, cycles=%d, inventory=%d) ===",
                symbol, total_pnl, total_cycles, net_inventory)
    logger.info("  Closed groups: %d, Open groups: %d",
                len(closed_groups), len(open_groups))

    if dry_run:
        logger.info("  [DRY RUN] Would create session, pair, %d closed cycles, %d open cycles",
                    len(closed_groups), len(open_groups))
        return

    # Create session
    session_id = db.create_session('tollgate', {
        'symbol': symbol,
        'anchor_price': anchor,
        'spacing': spacing,
        'net_inventory': net_inventory,
        'source': 'backfill'
    })

    # Create pair (direct, no secondary)
    pair_id = db.create_pair(
        session_id=session_id,
        primary_ticker=symbol,
        secondary_ticker='CASH',
        pair_type='direct',
        anchor_price=anchor,
        grid_spacing=spacing,
        levels_per_side=10,
        qty_per_level=4000,
        product='CNC'
    )

    running_pnl = 0.0

    # Import closed groups (none for SPCENET currently, but handle them)
    for g in closed_groups:
        group_id = g['group_id']
        bot_id = g.get('bot', 'A')
        grid_level = g.get('subset_index', 0)
        entry_side = g.get('entry_side', 'BUY')
        entry_price = g.get('entry_price', 0)
        target_price = g.get('target_price', 0)
        g_qty = g.get('qty', 4000)
        cycle_number = g.get('cycle_number', 1)
        entry_fill = g.get('entry_fill_price', entry_price)
        realized_pnl = g.get('realized_pnl', 0)

        cycle_id = db.open_cycle(
            pair_id=pair_id, session_id=session_id,
            group_id=group_id, bot_id=bot_id,
            grid_level=grid_level, cycle_number=cycle_number,
            entry_side=entry_side, entry_price=entry_price,
            target_price=target_price, qty=g_qty
        )

        # Record ENTRY
        db.record_transaction(
            cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
            ticker=symbol, side=entry_side, qty=g_qty,
            price=entry_fill, txn_type='ENTRY',
            order_id=g.get('entry_order_id'), group_id=group_id
        )

        # Record TARGET
        target_side = 'SELL' if entry_side == 'BUY' else 'BUY'
        running_pnl += realized_pnl

        # Get target fill price from target_orders
        target_fill_price = 0
        for to in g.get('target_orders', []):
            if to.get('fill_price'):
                target_fill_price = to['fill_price']

        db.record_transaction(
            cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
            ticker=symbol, side=target_side, qty=g_qty,
            price=target_fill_price or target_price,
            txn_type='TARGET', group_id=group_id,
            pnl_increment=realized_pnl, running_session_pnl=running_pnl
        )

        db.close_cycle(cycle_id, entry_fill, target_fill_price or target_price,
                        realized_pnl, 0)

        closed_at = parse_ts(g.get('closed_at'))
        if closed_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tg_cycles SET closed_at = %s WHERE cycle_id = %s",
                               (closed_at, cycle_id))

    # Import open groups
    for gid, g in open_groups.items():
        group_id = g['group_id']
        bot_id = g.get('bot', 'A')
        grid_level = g.get('subset_index', 0)
        entry_side = g.get('entry_side', 'BUY')
        entry_price = g.get('entry_price', 0)
        target_price = g.get('target_price', 0)
        g_qty = g.get('qty', 4000)
        cycle_number = g.get('cycle_number', 1)
        entry_fill = g.get('entry_fill_price', 0)
        filled_so_far = g.get('entry_filled_so_far', 0)

        cycle_id = db.open_cycle(
            pair_id=pair_id, session_id=session_id,
            group_id=group_id, bot_id=bot_id,
            grid_level=grid_level, cycle_number=cycle_number,
            entry_side=entry_side, entry_price=entry_price,
            target_price=target_price, qty=g_qty
        )

        created_at = parse_ts(g.get('created_at'))
        if created_at:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE tg_cycles SET opened_at = %s WHERE cycle_id = %s",
                               (created_at, cycle_id))

        # Record ENTRY if filled
        if filled_so_far > 0 and entry_fill:
            db.record_transaction(
                cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
                ticker=symbol, side=entry_side, qty=filled_so_far,
                price=entry_fill, txn_type='ENTRY',
                order_id=g.get('entry_order_id'), group_id=group_id,
                net_inventory=net_inventory
            )
            entry_filled_at = parse_ts(g.get('entry_filled_at'))
            if entry_filled_at:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE tg_transactions SET ts = %s WHERE cycle_id = %s AND txn_type = 'ENTRY'",
                        (entry_filled_at, cycle_id))

            # Record partial target fills
            for to in g.get('target_orders', []):
                if to.get('filled_qty', 0) > 0 and to.get('fill_price'):
                    target_side = 'SELL' if entry_side == 'BUY' else 'BUY'
                    db.record_transaction(
                        cycle_id=cycle_id, pair_id=pair_id, session_id=session_id,
                        ticker=symbol, side=target_side, qty=to['filled_qty'],
                        price=to['fill_price'], txn_type='TARGET',
                        order_id=to.get('order_id'), group_id=group_id,
                        is_partial=True
                    )

    # Upsert inventory
    if net_inventory != 0:
        db.upsert_inventory(session_id, symbol, net_inventory, anchor)

    # Update pair and session totals
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tg_pairs SET pair_pnl = %s, pair_cycles = %s WHERE pair_id = %s",
            (total_pnl, total_cycles, pair_id))
        cursor.execute(
            "UPDATE tg_sessions SET total_pnl = %s, total_cycles = %s WHERE session_id = %s",
            (total_pnl, total_cycles, session_id))

    logger.info("  Backfilled %s: session=%d, pair=%d, %d closed + %d open cycles, inventory=%d",
                symbol, session_id, pair_id, len(closed_groups), len(open_groups), net_inventory)

    return session_id, pair_id


def main():
    parser = argparse.ArgumentParser(description='Backfill PnL DB from JSON state files')
    parser.add_argument('--apply', action='store_true',
                        help='Actually insert into DB (default is dry-run)')
    args = parser.parse_args()

    dry_run = not args.apply
    if dry_run:
        logger.info("=== DRY RUN MODE (use --apply to actually insert) ===\n")
    else:
        logger.info("=== APPLYING TO DATABASE ===\n")

    db = None
    if not dry_run:
        db = PnLDBManager()
        db.ensure_schema()

    # Load TG config
    tg_config = load_json(TG_CONFIG_PATH)
    if not tg_config:
        logger.error("Could not load TG config from %s", TG_CONFIG_PATH)
        return

    # Process each TG Grid Bot state file
    for primary in tg_config.get('primaries', []):
        symbol = primary['symbol']
        state_path = os.path.join(TG_STATE_DIR, f'{symbol}_grid_state.json')
        state_data = load_json(state_path)
        if state_data:
            backfill_tg_grid(db, tg_config, state_data, symbol, dry_run=dry_run)
        else:
            logger.warning("No state file for %s", symbol)

    # Process TollGate state files
    if os.path.isdir(TOLLGATE_STATE_DIR):
        for fname in os.listdir(TOLLGATE_STATE_DIR):
            if fname.endswith('_tollgate_state.json'):
                state_path = os.path.join(TOLLGATE_STATE_DIR, fname)
                state_data = load_json(state_path)
                if state_data:
                    backfill_tollgate(db, state_data, dry_run=dry_run)

    if db:
        # Final summary
        with db.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("SELECT COUNT(*) as cnt FROM tg_sessions")
            sessions = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM tg_pairs")
            pairs = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM tg_cycles")
            cycles = cursor.fetchone()['cnt']
            cursor.execute("SELECT COUNT(*) as cnt FROM tg_transactions")
            txns = cursor.fetchone()['cnt']
            cursor.execute("SELECT COALESCE(SUM(total_pnl), 0) as total FROM tg_sessions")
            total_pnl = cursor.fetchone()['total']

        logger.info("\n=== BACKFILL COMPLETE ===")
        logger.info("Sessions: %d", sessions)
        logger.info("Pairs: %d", pairs)
        logger.info("Cycles: %d", cycles)
        logger.info("Transactions: %d", txns)
        logger.info("Total PnL: %.2f", total_pnl)

        db.close()

    logger.info("\nDone!")


if __name__ == '__main__':
    main()
