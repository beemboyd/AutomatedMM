#!/usr/bin/env python3
"""
TG Morning Warmup — Prepare grid bot system for the trading day.

Designed to run at 9:00 AM IST (weekdays) via launchd, or manually.

Steps:
1. Kill leftover bot/dashboard processes from previous session
2. Fresh XTS login (delete stale session, connect, save new)
3. Cancel all OPEN/PARTIAL orders from previous session
4. Reset state files (clear open_groups, preserve history)
5. Start dashboards (monitor 7777, config 7779)
6. Start all enabled bots
7. Verify bots placed orders (check state files after 15s)

Usage:
    python3 -m TG.warmup                    # Full warmup
    python3 -m TG.warmup --skip-bots        # Dashboards only
    python3 -m TG.warmup --skip-dashboards  # Bots only
    python3 -m TG.warmup --dry-run          # Log what would happen
    python3 -m TG.warmup --verify-only      # Check running processes
    python3 -m TG.warmup --skip-verify      # Skip order verification
"""

import sys
import os
import json
import signal
import logging
import argparse
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TG.hybrid_client import HybridClient

# Default XTS credentials (same as run.py / eod_flatten.py)
_DEFAULT_INTERACTIVE_KEY = 'YOUR_XTS_INTERACTIVE_KEY'
_DEFAULT_INTERACTIVE_SECRET = 'YOUR_XTS_INTERACTIVE_SECRET'
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TG_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(TG_DIR, 'state')
LOG_DIR = os.path.join(TG_DIR, 'logs')
CONFIG_FILE = os.path.join(STATE_DIR, 'tg_config.json')
SESSION_FILE = os.path.join(STATE_DIR, '.xts_session.json')
PID_FILE = os.path.join(STATE_DIR, '.bot_pids.json')

logger = logging.getLogger('TG.warmup')


def setup_logging():
    """Dual handler: stdout + warmup.log."""
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(LOG_DIR, 'warmup.log'),
                mode='a',
            ),
        ],
    )


def load_config() -> dict:
    """Load tg_config.json or return empty dict."""
    if not os.path.exists(CONFIG_FILE):
        logger.error("Config file not found: %s", CONFIG_FILE)
        return {}
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return {}


def kill_leftover_processes(dry_run: bool = False) -> int:
    """
    Kill stale bot and dashboard processes.

    1. Read PIDs from .bot_pids.json and kill them
    2. pgrep for TG.run and TG.dashboard processes
    """
    killed = 0

    # Step 1: Kill from PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
            for symbol, pid in pids.items():
                if dry_run:
                    logger.info("[DRY RUN] Would kill bot %s (PID=%s)", symbol, pid)
                    killed += 1
                else:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        killed += 1
                        logger.info("Killed bot %s (PID=%s) from PID file", symbol, pid)
                    except ProcessLookupError:
                        logger.info("Bot %s (PID=%s) already dead", symbol, pid)
                    except Exception as e:
                        logger.warning("Failed to kill bot %s (PID=%s): %s", symbol, pid, e)
            # Clear PID file
            if not dry_run:
                with open(PID_FILE, 'w') as f:
                    json.dump({}, f)
        except Exception as e:
            logger.warning("Error reading PID file: %s", e)

    # Step 2: pgrep for any remaining TG processes
    for pattern in ['TG.run', 'TG.dashboard']:
        try:
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True, text=True,
            )
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                pid = pid.strip()
                if pid and pid.isdigit():
                    # Skip our own PID
                    if int(pid) == os.getpid():
                        continue
                    if dry_run:
                        logger.info("[DRY RUN] Would kill %s process (PID=%s)", pattern, pid)
                        killed += 1
                    else:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            killed += 1
                            logger.info("Killed %s process (PID=%s) via pgrep", pattern, pid)
                        except ProcessLookupError:
                            pass
                        except Exception as e:
                            logger.warning("Failed to kill PID=%s: %s", pid, e)
        except Exception as e:
            logger.warning("pgrep for %s failed: %s", pattern, e)

    if killed == 0:
        logger.info("No leftover processes found")

    return killed


def fresh_xts_login(config: dict, dry_run: bool = False) -> HybridClient:
    """
    Delete old session file, do a fresh XTS login, return connected client.

    Returns None on failure.
    """
    interactive_key = config.get('xts_interactive_key', _DEFAULT_INTERACTIVE_KEY)
    interactive_secret = config.get('xts_interactive_secret', _DEFAULT_INTERACTIVE_SECRET)
    xts_root = config.get('xts_root', _DEFAULT_XTS_ROOT)
    zerodha_user = config.get('zerodha_user', 'Sai')

    # Delete stale session file to force fresh login
    if os.path.exists(SESSION_FILE):
        if dry_run:
            logger.info("[DRY RUN] Would delete session file: %s", SESSION_FILE)
        else:
            os.remove(SESSION_FILE)
            logger.info("Deleted stale session file: %s", SESSION_FILE)

    if dry_run:
        logger.info("[DRY RUN] Would connect to XTS (key=%s...)", interactive_key[:8])
        return None

    client = HybridClient(
        interactive_key=interactive_key,
        interactive_secret=interactive_secret,
        zerodha_user=zerodha_user,
        root_url=xts_root,
    )
    if not client.connect():
        logger.error("XTS connection failed")
        return None

    logger.info("XTS fresh login OK: userID=%s", client.client_id)
    return client


def cancel_stale_orders(client: HybridClient, dry_run: bool = False) -> int:
    """Cancel all OPEN/PARTIAL orders on XTS."""
    if dry_run:
        logger.info("[DRY RUN] Would cancel all open/partial orders")
        return 0

    orders = client.get_orders()
    cancelled = 0
    for o in orders:
        if o['status'] in ('OPEN', 'PARTIAL'):
            oid = o['order_id']
            uid = o.get('order_unique_id', '')
            if client.cancel_order(oid, uid):
                cancelled += 1
                logger.info("Cancelled stale order %s [%s]", oid, uid)
            else:
                logger.error("Failed to cancel order %s", oid)
    return cancelled


def reset_state_files(config: dict, dry_run: bool = False) -> int:
    """
    Reset state files for each primary: clear open_groups and order_to_group,
    preserve closed_groups, total_pnl, total_cycles.
    """
    primaries = config.get('primaries', [])
    reset_count = 0

    for primary in primaries:
        symbol = primary.get('symbol', '')
        if not symbol:
            continue

        state_file = os.path.join(STATE_DIR, f'{symbol}_grid_state.json')
        if not os.path.exists(state_file):
            logger.info("No state file for %s, skipping reset", symbol)
            continue

        try:
            with open(state_file) as f:
                state = json.load(f)

            open_count = len(state.get('open_groups', {}))
            order_count = len(state.get('order_to_group', {}))

            if dry_run:
                logger.info("[DRY RUN] Would reset %s state: "
                            "clear %d open_groups, %d order mappings",
                            symbol, open_count, order_count)
                reset_count += 1
                continue

            # Move any remaining open groups to closed with CANCELLED status
            open_groups = state.get('open_groups', {})
            closed_groups = state.get('closed_groups', [])
            for gid, group in open_groups.items():
                group['status'] = 'CANCELLED'
                group['closed_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
                closed_groups.append(group)

            # Reset open state, preserve history
            state['open_groups'] = {}
            state['order_to_group'] = {}
            state['closed_groups'] = closed_groups

            # Atomic write
            tmp = state_file + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, state_file)

            logger.info("Reset %s state: moved %d open groups to cancelled, "
                        "cleared %d order mappings, preserved %d closed groups",
                        symbol, open_count, order_count, len(closed_groups))
            reset_count += 1

        except Exception as e:
            logger.error("Failed to reset state for %s: %s", symbol, e)

    return reset_count


def start_dashboards(dry_run: bool = False) -> list:
    """Launch monitor (7777) and config (7779) dashboards as background subprocesses."""
    os.makedirs(LOG_DIR, exist_ok=True)
    procs = []

    dashboards = [
        {'mode': 'monitor', 'port': 7777},
        {'mode': 'config', 'port': 7779},
    ]

    for dash in dashboards:
        cmd = [
            sys.executable, '-m', 'TG.dashboard',
            '--port', str(dash['port']),
            '--mode', dash['mode'],
        ]

        if dry_run:
            logger.info("[DRY RUN] Would start dashboard: %s", ' '.join(cmd))
            continue

        log_file = os.path.join(LOG_DIR, f"dashboard_{dash['mode']}.log")
        with open(log_file, 'a') as lf:
            proc = subprocess.Popen(
                cmd, cwd=PROJECT_ROOT,
                stdout=lf, stderr=subprocess.STDOUT,
            )
        procs.append(proc)
        logger.info("Started %s dashboard on port %d (PID=%d)",
                     dash['mode'], dash['port'], proc.pid)

    return procs


def start_bots(config: dict, dry_run: bool = False) -> int:
    """Launch each enabled primary as a TG.run subprocess."""
    primaries = config.get('primaries', [])
    started = 0

    for primary in primaries:
        symbol = primary.get('symbol', '')
        if not symbol:
            continue

        if not primary.get('enabled', True):
            logger.info("Bot %s is disabled, skipping", symbol)
            continue

        cmd = [
            sys.executable, '-m', 'TG.run',
            '--symbol', symbol,
            '--pair-symbol', config.get('secondary_symbol', ''),
            '--hedge-ratio', str(primary.get('hedge_ratio', 0)),
            '--partial-hedge-ratio', str(primary.get('partial_hedge_ratio', 0)),
            '--grid-space', str(primary.get('grid_space', 0.01)),
            '--target', str(primary.get('target', 0.02)),
            '--levels-per-side', str(primary.get('levels_per_side', 10)),
            '--qty-per-level', str(primary.get('qty_per_level', 100)),
            '--holdings', str(primary.get('holdings_override', -1)),
            '--product', primary.get('product', 'NRML'),
            '--interactive-key', config.get('xts_interactive_key', ''),
            '--interactive-secret', config.get('xts_interactive_secret', ''),
            '--user', config.get('zerodha_user', 'Sai'),
            '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
            '--poll-interval', str(primary.get('poll_interval', 2.0)),
            '--reanchor-epoch', str(primary.get('reanchor_epoch', 100)),
            '--max-grid-levels', str(primary.get('max_grid_levels', 2000)),
        ]

        if primary.get('auto_anchor'):
            cmd.append('--auto-anchor')
        else:
            anchor = primary.get('anchor_price', 0)
            if anchor > 0:
                cmd.extend(['--anchor', str(anchor)])
            else:
                cmd.append('--auto-anchor')

        if dry_run:
            logger.info("[DRY RUN] Would start bot: %s", ' '.join(cmd))
            started += 1
            continue

        log_file = os.path.join(LOG_DIR, f'{symbol}_bot.log')
        os.makedirs(LOG_DIR, exist_ok=True)

        with open(log_file, 'a') as lf:
            proc = subprocess.Popen(
                cmd, cwd=PROJECT_ROOT,
                stdout=lf, stderr=subprocess.STDOUT,
            )

        # Record PID in shared file
        pids = {}
        if os.path.exists(PID_FILE):
            try:
                with open(PID_FILE) as f:
                    pids = json.load(f)
            except Exception:
                pass
        pids[symbol] = proc.pid
        tmp = PID_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(pids, f, indent=2)
        os.replace(tmp, PID_FILE)

        logger.info("Started bot %s (PID=%d)", symbol, proc.pid)
        started += 1

    return started


def verify_bots(config: dict, wait_seconds: int = 15) -> bool:
    """
    Wait and check state files for open groups to confirm bots placed orders.

    Returns True if at least one bot has open groups.
    """
    primaries = config.get('primaries', [])
    enabled = [p for p in primaries if p.get('enabled', True) and p.get('symbol')]
    if not enabled:
        logger.warning("No enabled primaries to verify")
        return False

    logger.info("Waiting %ds for bots to place orders...", wait_seconds)
    time.sleep(wait_seconds)

    all_ok = True
    for primary in enabled:
        symbol = primary['symbol']
        state_file = os.path.join(STATE_DIR, f'{symbol}_grid_state.json')

        if not os.path.exists(state_file):
            logger.warning("VERIFY FAIL: %s — no state file", symbol)
            all_ok = False
            continue

        try:
            with open(state_file) as f:
                state = json.load(f)
            open_count = len(state.get('open_groups', {}))
            if open_count > 0:
                logger.info("VERIFY OK: %s — %d open groups", symbol, open_count)
            else:
                logger.warning("VERIFY FAIL: %s — 0 open groups", symbol)
                all_ok = False
        except Exception as e:
            logger.warning("VERIFY FAIL: %s — %s", symbol, e)
            all_ok = False

    # Check PID file for running processes
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
            for symbol, pid in pids.items():
                try:
                    os.kill(int(pid), 0)
                    logger.info("Process alive: %s (PID=%d)", symbol, pid)
                except ProcessLookupError:
                    logger.warning("Process dead: %s (PID=%d)", symbol, pid)
                    all_ok = False
        except Exception:
            pass

    return all_ok


def verify_only(config: dict):
    """Check currently running processes without starting anything."""
    logger.info("=" * 60)
    logger.info("VERIFY ONLY — Checking running processes")
    logger.info("=" * 60)

    # Check PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
            if pids:
                for symbol, pid in pids.items():
                    try:
                        os.kill(int(pid), 0)
                        logger.info("Bot %s: RUNNING (PID=%d)", symbol, pid)
                    except ProcessLookupError:
                        logger.info("Bot %s: DEAD (PID=%d)", symbol, pid)
            else:
                logger.info("No bots in PID file")
        except Exception as e:
            logger.warning("Error reading PID file: %s", e)
    else:
        logger.info("No PID file found")

    # pgrep for TG processes
    for pattern in ['TG.run', 'TG.dashboard']:
        try:
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True, text=True,
            )
            pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip().isdigit()]
            if pids:
                logger.info("%s processes: %s", pattern, ', '.join(pids))
            else:
                logger.info("%s processes: none", pattern)
        except Exception:
            pass

    # Check state files
    primaries = config.get('primaries', [])
    for primary in primaries:
        symbol = primary.get('symbol', '')
        if not symbol:
            continue
        state_file = os.path.join(STATE_DIR, f'{symbol}_grid_state.json')
        if os.path.exists(state_file):
            try:
                with open(state_file) as f:
                    state = json.load(f)
                open_count = len(state.get('open_groups', {}))
                closed_count = len(state.get('closed_groups', []))
                pnl = state.get('total_pnl', 0)
                logger.info("State %s: %d open, %d closed, PnL=%.2f",
                            symbol, open_count, closed_count, pnl)
            except Exception as e:
                logger.warning("State %s: error — %s", symbol, e)
        else:
            logger.info("State %s: no file", symbol)


def main():
    parser = argparse.ArgumentParser(description='TG Morning Warmup')
    parser.add_argument('--skip-bots', action='store_true',
                        help='Skip starting bots (dashboards only)')
    parser.add_argument('--skip-dashboards', action='store_true',
                        help='Skip starting dashboards (bots only)')
    parser.add_argument('--skip-verify', action='store_true',
                        help='Skip order verification step')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log what would happen without executing')
    parser.add_argument('--verify-only', action='store_true',
                        help='Check running processes and exit')
    parser.add_argument('--interactive-key', default=_DEFAULT_INTERACTIVE_KEY)
    parser.add_argument('--interactive-secret', default=_DEFAULT_INTERACTIVE_SECRET)
    parser.add_argument('--xts-root', default=_DEFAULT_XTS_ROOT)
    parser.add_argument('--user', default='Sai', help='Zerodha user for market data')
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    setup_logging()

    logger.info("=" * 60)
    logger.info("TG MORNING WARMUP")
    logger.info("=" * 60)

    # Load config
    config = load_config()
    if not config:
        logger.error("No config loaded. Create %s first.", CONFIG_FILE)
        sys.exit(1)

    # Override credentials from CLI if provided
    if args.interactive_key != _DEFAULT_INTERACTIVE_KEY:
        config['xts_interactive_key'] = args.interactive_key
    if args.interactive_secret != _DEFAULT_INTERACTIVE_SECRET:
        config['xts_interactive_secret'] = args.interactive_secret
    if args.xts_root != _DEFAULT_XTS_ROOT:
        config['xts_root'] = args.xts_root
    if args.user != 'Sai':
        config['zerodha_user'] = args.user

    # Verify-only mode
    if args.verify_only:
        verify_only(config)
        return

    dry_run = args.dry_run
    if dry_run:
        logger.info("*** DRY RUN MODE — no actions will be taken ***")

    # Step 1: Kill leftover processes
    logger.info("Step 1: Killing leftover processes...")
    killed = kill_leftover_processes(dry_run=dry_run)
    logger.info("Killed %d processes", killed)
    if killed > 0 and not dry_run:
        time.sleep(2)  # Give processes time to exit

    # Step 2: Fresh XTS login
    logger.info("Step 2: Fresh XTS login...")
    client = fresh_xts_login(config, dry_run=dry_run)
    if not dry_run and client is None:
        logger.error("XTS login failed. Aborting warmup.")
        sys.exit(1)

    # Step 3: Cancel stale orders
    logger.info("Step 3: Cancelling stale orders...")
    cancelled = cancel_stale_orders(client, dry_run=dry_run)
    logger.info("Cancelled %d stale orders", cancelled)

    # Step 4: Reset state files
    logger.info("Step 4: Resetting state files...")
    reset = reset_state_files(config, dry_run=dry_run)
    logger.info("Reset %d state files", reset)

    # Step 5: Start dashboards
    if not args.skip_dashboards:
        logger.info("Step 5: Starting dashboards...")
        start_dashboards(dry_run=dry_run)
    else:
        logger.info("Step 5: Skipping dashboards (--skip-dashboards)")

    # Step 6: Start bots
    if not args.skip_bots:
        logger.info("Step 6: Starting bots...")
        started = start_bots(config, dry_run=dry_run)
        logger.info("Started %d bots", started)
    else:
        logger.info("Step 6: Skipping bots (--skip-bots)")

    # Step 7: Verify
    if not args.skip_bots and not args.skip_verify and not dry_run:
        logger.info("Step 7: Verifying bots...")
        ok = verify_bots(config)
        if ok:
            logger.info("All bots verified OK")
        else:
            logger.warning("Some bots failed verification — check logs")
    else:
        logger.info("Step 7: Skipping verification")

    logger.info("=" * 60)
    logger.info("WARMUP COMPLETE")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
