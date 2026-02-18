#!/usr/bin/env python3
"""
TollGate Morning Warmup — Prepare SPCENET market-making bot for the trading day.

Designed to run at 9:10 AM IST (weekdays) via launchd, 10 min after main TG warmup.

Steps:
1. Kill leftover TollGate processes from previous session
2. Fresh XTS login (delete stale session, connect TollGateClient)
3. Cancel all OPEN/PARTIAL orders from previous session
4. Reset state (move open_groups -> closed as CANCELLED, clear order_to_group)
5. Start engine (python -m TG.TollGate.run --auto-anchor as subprocess)
6. Verify (wait 15s, check state file for open_groups > 0, confirm PID alive)

Config loaded from TG/TollGate/state/tollgate_config.json (same file dashboard uses).

Usage:
    python3 -m TG.TollGate.warmup                # Full warmup
    python3 -m TG.TollGate.warmup --dry-run      # Log what would happen
    python3 -m TG.TollGate.warmup --verify-only   # Check running processes
    python3 -m TG.TollGate.warmup --skip-verify   # Skip order verification
"""

import sys
import os
import json
import signal
import logging
import argparse
import subprocess
import time

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TG_TOLLGATE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(TG_TOLLGATE_DIR, 'state')
LOG_DIR = os.path.join(TG_TOLLGATE_DIR, 'logs')
CONFIG_FILE = os.path.join(STATE_DIR, 'tollgate_config.json')
SESSION_FILE = os.path.join(STATE_DIR, '.xts_session.json')
PID_FILE = os.path.join(STATE_DIR, '.bot_pids.json')
STATE_FILE = os.path.join(STATE_DIR, 'SPCENET_tollgate_state.json')

logger = logging.getLogger('TG.TollGate.warmup')


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
    """Load tollgate_config.json or return defaults."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load config: %s", e)

    # Fallback defaults
    return {
        "interactive_key": "1d17edd135146be7572510",
        "interactive_secret": "Htvy720#4K",
        "marketdata_key": "202e06ba0b421bf9e1e515",
        "marketdata_secret": "Payr544@nk",
        "xts_root": "https://xts.myfindoc.com",
        "auto_anchor": True,
    }


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def kill_leftover_processes(dry_run: bool = False) -> int:
    """
    Kill stale TollGate processes.

    1. Read PIDs from .bot_pids.json and kill them
    2. pgrep for TG.TollGate.run processes
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

    # Step 2: pgrep for any remaining TollGate processes
    for pattern in ['TG.TollGate.run']:
        try:
            result = subprocess.run(
                ['pgrep', '-f', pattern],
                capture_output=True, text=True,
            )
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                pid = pid.strip()
                if pid and pid.isdigit():
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


def fresh_xts_login(config: dict, dry_run: bool = False):
    """
    Delete old session file, do a fresh XTS login via TollGateClient.

    Returns connected TollGateClient or None.
    """
    interactive_key = config.get('interactive_key', '1d17edd135146be7572510')
    interactive_secret = config.get('interactive_secret', 'Htvy720#4K')
    marketdata_key = config.get('marketdata_key', '202e06ba0b421bf9e1e515')
    marketdata_secret = config.get('marketdata_secret', 'Payr544@nk')
    xts_root = config.get('xts_root', 'https://xts.myfindoc.com')

    # Delete stale session file to force fresh login
    if os.path.exists(SESSION_FILE):
        if dry_run:
            logger.info("[DRY RUN] Would delete session file: %s", SESSION_FILE)
        else:
            os.remove(SESSION_FILE)
            logger.info("Deleted stale session file: %s", SESSION_FILE)

    if dry_run:
        logger.info("[DRY RUN] Would connect to XTS (interactive=%s..., marketdata=%s...)",
                     interactive_key[:8], marketdata_key[:8])
        return None

    from TG.TollGate.client import TollGateClient
    client = TollGateClient(
        interactive_key=interactive_key,
        interactive_secret=interactive_secret,
        marketdata_key=marketdata_key,
        marketdata_secret=marketdata_secret,
        root_url=xts_root,
    )
    if not client.connect():
        logger.error("XTS connection failed")
        return None

    logger.info("XTS fresh login OK: userID=%s", client.client_id)
    return client


def cancel_stale_orders(client, dry_run: bool = False) -> int:
    """Cancel all OPEN/PARTIAL orders on XTS."""
    if dry_run:
        logger.info("[DRY RUN] Would cancel all open/partial orders")
        return 0

    orders = client.get_orders()
    if orders is None:
        logger.error("Failed to fetch order book")
        return 0

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


def reset_state(dry_run: bool = False) -> bool:
    """
    Reset TollGate state: move open_groups -> closed as CANCELLED,
    clear order_to_group, preserve PnL/history.
    """
    if not os.path.exists(STATE_FILE):
        logger.info("No state file found, nothing to reset")
        return True

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)

        open_count = len(state.get('open_groups', {}))
        order_count = len(state.get('order_to_group', {}))

        if open_count == 0 and order_count == 0:
            logger.info("State already clean: 0 open groups, 0 order mappings")
            return True

        if dry_run:
            logger.info("[DRY RUN] Would reset state: clear %d open_groups, %d order mappings",
                        open_count, order_count)
            return True

        # Move remaining open groups to closed with CANCELLED status
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
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)

        logger.info("Reset state: moved %d open groups to cancelled, "
                     "cleared %d order mappings, preserved %d closed groups",
                     open_count, order_count, len(closed_groups))
        return True

    except Exception as e:
        logger.error("Failed to reset state: %s", e)
        return False


def start_engine(config: dict, dry_run: bool = False) -> int:
    """
    Launch TG.TollGate.run --auto-anchor as subprocess.

    Returns PID of started process, or 0 on failure.
    """
    cmd = [
        sys.executable, '-m', 'TG.TollGate.run',
        '--interactive-key', config.get('interactive_key', ''),
        '--interactive-secret', config.get('interactive_secret', ''),
        '--marketdata-key', config.get('marketdata_key', ''),
        '--marketdata-secret', config.get('marketdata_secret', ''),
        '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
        '--spacing', str(config.get('base_spacing', 0.01)),
        '--profit', str(config.get('round_trip_profit', 0.01)),
        '--levels', str(config.get('levels_per_side', 10)),
        '--qty', str(config.get('qty_per_level', 4000)),
        '--product', config.get('product', 'CNC'),
        '--poll-interval', str(config.get('poll_interval', 2.0)),
        '--max-reanchors', str(config.get('max_reanchors', 100)),
    ]

    if config.get('auto_anchor', True):
        cmd.append('--auto-anchor')
    else:
        anchor = config.get('anchor_price', 0)
        if anchor > 0:
            cmd.extend(['--anchor', str(anchor)])
        else:
            cmd.append('--auto-anchor')

    if dry_run:
        logger.info("[DRY RUN] Would start: %s", ' '.join(cmd))
        return 0

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, 'tollgate_engine.log')

    with open(log_file, 'a') as lf:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT,
            stdout=lf, stderr=subprocess.STDOUT,
        )

    # Record PID
    pids = {}
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
        except Exception:
            pass
    pids['SPCENET'] = proc.pid
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = PID_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(pids, f, indent=2)
    os.replace(tmp, PID_FILE)

    logger.info("Started TollGate engine (PID=%d)", proc.pid)
    return proc.pid


def verify_bot(wait_seconds: int = 15) -> bool:
    """
    Wait and verify the TollGate bot placed orders and is alive.

    Checks:
    1. PID from .bot_pids.json is alive
    2. State file has open_groups > 0
    """
    logger.info("Waiting %ds for bot to place orders...", wait_seconds)
    time.sleep(wait_seconds)

    # Check PID
    pid = None
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
            pid = pids.get('SPCENET')
        except Exception:
            pass

    if pid is None:
        logger.warning("VERIFY FAIL: no PID found in PID file")
        return False

    if not _pid_alive(pid):
        logger.warning("VERIFY FAIL: process PID=%d is dead", pid)
        return False

    logger.info("Process alive: PID=%d", pid)

    # Check state file
    if not os.path.exists(STATE_FILE):
        logger.warning("VERIFY FAIL: no state file")
        return False

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
        open_count = len(state.get('open_groups', {}))
        if open_count > 0:
            logger.info("VERIFY OK: %d open groups, PID=%d alive", open_count, pid)
            return True
        else:
            logger.warning("VERIFY FAIL: 0 open groups (PID=%d alive)", pid)
            return False
    except Exception as e:
        logger.warning("VERIFY FAIL: state read error: %s", e)
        return False


def verify_only():
    """Check currently running TollGate processes without starting anything."""
    logger.info("=" * 60)
    logger.info("VERIFY ONLY — Checking TollGate processes")
    logger.info("=" * 60)

    # Check PID file
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pids = json.load(f)
            if pids:
                for symbol, pid in pids.items():
                    if _pid_alive(pid):
                        logger.info("Bot %s: RUNNING (PID=%d)", symbol, pid)
                    else:
                        logger.info("Bot %s: DEAD (PID=%d)", symbol, pid)
            else:
                logger.info("No bots in PID file")
        except Exception as e:
            logger.warning("Error reading PID file: %s", e)
    else:
        logger.info("No PID file found")

    # pgrep for TollGate processes
    for pattern in ['TG.TollGate.run']:
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

    # Check state file
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            open_count = len(state.get('open_groups', {}))
            closed_count = len(state.get('closed_groups', []))
            pnl = state.get('total_pnl', 0)
            inv = state.get('net_inventory', 0)
            logger.info("State: %d open, %d closed, PnL=%.2f, inventory=%d",
                        open_count, closed_count, pnl, inv)
        except Exception as e:
            logger.warning("State error: %s", e)
    else:
        logger.info("No state file found")


def main():
    parser = argparse.ArgumentParser(description='TollGate Morning Warmup')
    parser.add_argument('--skip-verify', action='store_true',
                        help='Skip order verification step')
    parser.add_argument('--dry-run', action='store_true',
                        help='Log what would happen without executing')
    parser.add_argument('--verify-only', action='store_true',
                        help='Check running processes and exit')
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    setup_logging()

    logger.info("=" * 60)
    logger.info("TOLLGATE MORNING WARMUP")
    logger.info("=" * 60)

    # Load config
    config = load_config()

    # Verify-only mode
    if args.verify_only:
        verify_only()
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

    # Disconnect warmup client (engine will create its own)
    if client:
        client.stop()

    # Step 4: Reset state
    logger.info("Step 4: Resetting state...")
    reset_state(dry_run=dry_run)

    # Step 5: Start engine
    logger.info("Step 5: Starting TollGate engine...")
    pid = start_engine(config, dry_run=dry_run)
    if not dry_run and pid == 0:
        logger.error("Failed to start engine")
        sys.exit(1)
    if pid > 0:
        logger.info("Engine started with PID=%d", pid)

    # Step 6: Verify
    if not args.skip_verify and not dry_run:
        logger.info("Step 6: Verifying bot...")
        ok = verify_bot()
        if ok:
            logger.info("Bot verified OK")
        else:
            logger.warning("Bot verification failed — check logs")
    else:
        logger.info("Step 6: Skipping verification")

    logger.info("=" * 60)
    logger.info("TOLLGATE WARMUP COMPLETE")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
