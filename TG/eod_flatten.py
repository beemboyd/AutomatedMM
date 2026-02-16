#!/usr/bin/env python3
"""
TG EOD Flatten — Cancel all orders, flatten SPCENET pair positions, stop the bot.

Designed to run at 3:12 PM IST via cron/launchd before market close.

Steps:
1. Connect to XTS
2. Cancel ALL open orders (TATSILV entries, targets, SPCENET hedges)
3. Flatten net SPCENET position (buy back any short, sell any long)
4. Kill any running TG bot process
5. Save final state

Usage:
    python3 -m TG.eod_flatten --symbol TATSILV --pair-symbol SPCENET
"""

import sys
import os
import signal
import logging
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TG.hybrid_client import HybridClient

# Default XTS credentials (same as run.py)
_DEFAULT_INTERACTIVE_KEY = '59ec1c9e69270e5cd97108'
_DEFAULT_INTERACTIVE_SECRET = 'Mjcd080@xT'
_DEFAULT_XTS_ROOT = 'https://xts.myfindoc.com'

logger = logging.getLogger('TG.eod_flatten')


def setup_logging():
    fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(os.path.dirname(__file__), 'logs', 'eod_flatten.log'),
                mode='a',
            ),
        ],
    )


def cancel_all_open_orders(client: HybridClient) -> int:
    """Cancel all open/new orders on XTS."""
    orders = client.get_orders()
    cancelled = 0
    for o in orders:
        if o['status'] in ('OPEN', 'PARTIAL'):
            oid = o['order_id']
            uid = o.get('order_unique_id', '')
            if client.cancel_order(oid, uid):
                cancelled += 1
                logger.info("Cancelled order %s [%s]", oid, uid)
            else:
                logger.error("Failed to cancel order %s", oid)
    return cancelled


def flatten_pair_position(client: HybridClient, pair_symbol: str,
                          exchange: str = "NSE", product: str = "NRML"):
    """
    Flatten net position on pair symbol by calculating net from today's fills.

    Scans filled orders to compute net qty, then places an offsetting order.
    """
    orders = client.get_orders()

    # Calculate net qty from filled pair orders
    net_qty = 0
    for o in orders:
        uid = o.get('order_unique_id', '')
        if not uid.startswith('PR'):
            continue
        if o['status'] != 'COMPLETE':
            continue
        filled = int(o.get('filled_quantity', 0))
        side = o.get('transaction_type', '')
        if side == 'BUY':
            net_qty += filled
        elif side == 'SELL':
            net_qty -= filled

    logger.info("Net %s position from pair trades: %d", pair_symbol, net_qty)

    if net_qty == 0:
        logger.info("No %s position to flatten", pair_symbol)
        return

    # Flatten: if net_qty > 0, we're long → SELL; if < 0, we're short → BUY
    if net_qty > 0:
        side = "SELL"
        qty = net_qty
    else:
        side = "BUY"
        qty = abs(net_qty)

    logger.info("Flattening %s: %s %d", pair_symbol, side, qty)
    order_id, price = client.place_market_order(
        pair_symbol, side, qty, exchange, product,
        order_unique_id=f"FLAT_{pair_symbol}",
        slippage=0.05,  # wider slippage for EOD urgency
    )
    if order_id:
        logger.info("Flatten order placed: %s %s %d @ %.2f, order=%s",
                     side, pair_symbol, qty, price, order_id)
    else:
        logger.error("Flatten order FAILED: %s %s %d", side, pair_symbol, qty)


def kill_bot_process():
    """Find and kill any running TG.run process."""
    import subprocess
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'TG.run'],
            capture_output=True, text=True,
        )
        pids = result.stdout.strip().split('\n')
        killed = 0
        for pid in pids:
            pid = pid.strip()
            if pid and pid.isdigit():
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    killed += 1
                    logger.info("Killed bot process PID=%s", pid)
                except ProcessLookupError:
                    pass
        if killed == 0:
            logger.info("No running TG.run process found")
        return killed
    except Exception as e:
        logger.error("Error killing bot: %s", e)
        return 0


def main():
    parser = argparse.ArgumentParser(description='TG EOD Flatten')
    parser.add_argument('--symbol', default='TATSILV', help='Primary symbol')
    parser.add_argument('--pair-symbol', default='SPCENET', help='Pair symbol to flatten')
    parser.add_argument('--exchange', default='NSE')
    parser.add_argument('--product', default='NRML')
    parser.add_argument('--interactive-key', default=_DEFAULT_INTERACTIVE_KEY)
    parser.add_argument('--interactive-secret', default=_DEFAULT_INTERACTIVE_SECRET)
    parser.add_argument('--xts-root', default=_DEFAULT_XTS_ROOT)
    parser.add_argument('--user', default='Sai', help='Zerodha user for market data')
    args = parser.parse_args()

    os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)
    setup_logging()

    logger.info("=" * 60)
    logger.info("TG EOD FLATTEN — %s + %s", args.symbol, args.pair_symbol)
    logger.info("=" * 60)

    # Step 1: Kill the bot first so it doesn't place new orders
    logger.info("Step 1: Killing bot process...")
    kill_bot_process()

    # Step 2: Connect to XTS
    logger.info("Step 2: Connecting to XTS...")
    client = HybridClient(
        interactive_key=args.interactive_key,
        interactive_secret=args.interactive_secret,
        zerodha_user=args.user,
        root_url=args.xts_root,
    )
    if not client.connect():
        logger.error("XTS connection failed. Cannot flatten.")
        sys.exit(1)

    # Step 3: Cancel all open orders
    logger.info("Step 3: Cancelling all open orders...")
    cancelled = cancel_all_open_orders(client)
    logger.info("Cancelled %d orders", cancelled)

    # Step 4: Flatten pair position
    logger.info("Step 4: Flattening %s position...", args.pair_symbol)
    flatten_pair_position(client, args.pair_symbol, args.exchange, args.product)

    logger.info("=" * 60)
    logger.info("EOD FLATTEN COMPLETE")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
