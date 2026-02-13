#!/usr/bin/env python
"""
Grid Trading Bot — Entry Point (XTS trading + Zerodha market data)

Usage:
    # Start grid bot (Zerodha user defaults to Sai)
    python -m TG.run --symbol IRFC --anchor 50.25

    # Custom grid parameters
    python -m TG.run --symbol IRFC --anchor 50.25 \\
        --grid-space 0.05 --target 0.10 \\
        --total-qty 1000 --subset-qty 300

    # Dry run (print grid layout without trading)
    python -m TG.run --symbol IRFC --anchor 50.25 --dry-run

    # Use current LTP as anchor (fetches from Zerodha)
    python -m TG.run --symbol IRFC --auto-anchor

    # Cancel all open orders and exit
    python -m TG.run --symbol IRFC --anchor 50.25 --cancel-all

    # Custom XTS credentials + Zerodha user
    python -m TG.run --symbol IRFC --anchor 50.25 \\
        --interactive-key YOUR_KEY --interactive-secret YOUR_SECRET \\
        --user Sai
"""

import sys
import os
import argparse
import logging

# Ensure project root is on path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TG.config import GridConfig
from TG.engine import GridEngine
from TG.hybrid_client import _load_zerodha_credentials

from kiteconnect import KiteConnect

# Default XTS credentials
_DEFAULT_INTERACTIVE_KEY = '59ec1c9e69270e5cd97108'
_DEFAULT_INTERACTIVE_SECRET = 'Mjcd080@xT'
_DEFAULT_MARKETDATA_KEY = '202e06ba0b421bf9e1e515'
_DEFAULT_MARKETDATA_SECRET = 'Payr544@nk'
_DEFAULT_XTS_ROOT = 'https://developers.symphonyfintech.in'


def setup_logging(log_level: str = "INFO"):
    """Configure logging to console and file."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'grid_engine.log')

    fmt = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, mode='a'),
        ],
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description='TG — Grid Trading Bot (XTS trading + Zerodha data)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('--symbol', required=True,
                        help='NSE trading symbol (e.g., IRFC)')
    parser.add_argument('--anchor', type=float, default=None,
                        help='Anchor price (grid center)')
    parser.add_argument('--auto-anchor', action='store_true',
                        help='Use current LTP as anchor price')

    # Grid parameters
    parser.add_argument('--grid-space', type=float, default=0.01,
                        help='Base grid spacing in INR (default: 0.01 = 1 paisa)')
    parser.add_argument('--target', type=float, default=0.02,
                        help='Base target offset in INR (default: 0.02 = 2 paisa)')
    parser.add_argument('--total-qty', type=int, default=1000,
                        help='Total position size (default: 1000)')
    parser.add_argument('--subset-qty', type=int, default=300,
                        help='Quantity per grid subset (default: 300)')

    # Broker parameters
    parser.add_argument('--exchange', default='NSE',
                        help='Exchange (default: NSE)')
    parser.add_argument('--product', default='NRML',
                        help='Product type: NRML (carry-forward) or MIS (default: NRML)')

    # Credentials
    parser.add_argument('--interactive-key', default=_DEFAULT_INTERACTIVE_KEY,
                        help='XTS Interactive API key')
    parser.add_argument('--interactive-secret', default=_DEFAULT_INTERACTIVE_SECRET,
                        help='XTS Interactive API secret')
    parser.add_argument('--user', default='Sai',
                        help='Zerodha user for market data (default: Sai)')
    parser.add_argument('--xts-root', default=_DEFAULT_XTS_ROOT,
                        help='XTS API root URL')

    # Operational
    parser.add_argument('--poll-interval', type=float, default=2.0,
                        help='Order poll interval in seconds (default: 2.0)')
    parser.add_argument('--no-reenter', action='store_true',
                        help='Disable auto re-entry after target fill')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')

    # Actions
    parser.add_argument('--dry-run', action='store_true',
                        help='Print grid layout and exit without trading')
    parser.add_argument('--cancel-all', action='store_true',
                        help='Cancel all open orders and exit')

    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.log_level)
    logger = logging.getLogger('TG')

    # Resolve anchor price
    anchor_price = args.anchor
    if args.auto_anchor:
        logger.info("Fetching LTP for %s from Zerodha (user=%s)...",
                     args.symbol, args.user)
        try:
            creds = _load_zerodha_credentials(args.user)
            kite = KiteConnect(api_key=creds['api_key'])
            kite.set_access_token(creds['access_token'])
            key = f"{args.exchange}:{args.symbol}"
            data = kite.ltp([key])
            ltp = data[key]['last_price']
            if ltp is None:
                logger.error("Could not fetch LTP for %s. Cannot auto-anchor.", args.symbol)
                sys.exit(1)
            anchor_price = ltp
            logger.info("Auto-anchor: %s LTP = %.2f", args.symbol, anchor_price)
        except Exception as e:
            logger.error("Auto-anchor failed: %s", e)
            sys.exit(1)

    if anchor_price is None:
        logger.error("Anchor price required. Use --anchor or --auto-anchor.")
        sys.exit(1)

    # Build config
    config = GridConfig.from_args(
        symbol=args.symbol,
        anchor_price=anchor_price,
        base_grid_space=args.grid_space,
        base_target=args.target,
        total_qty=args.total_qty,
        subset_qty=args.subset_qty,
        exchange=args.exchange,
        product=args.product,
        interactive_key=args.interactive_key,
        interactive_secret=args.interactive_secret,
        zerodha_user=args.user,
        xts_root=args.xts_root,
        auto_reenter=not args.no_reenter,
        poll_interval=args.poll_interval,
    )

    # Dry run: just print the grid and exit
    if args.dry_run:
        config.print_grid_layout()
        subsets = config.compute_subsets()
        print(f"  Grid has {len(subsets)} subsets.")
        print(f"  All buy targets converge to {anchor_price + config.base_grid_space:.2f}")
        print(f"  All sell targets converge to {anchor_price - config.base_grid_space:.2f}")
        print(f"\n  This is a dry run. No orders placed.")
        return

    # Cancel all orders
    if args.cancel_all:
        engine = GridEngine(config)
        engine.client.connect()
        if engine.state.load():
            engine.buy_bot.restore_level_groups()
            engine.sell_bot.restore_level_groups()
        engine.cancel_all()
        return

    # Start the engine
    logger.info("Starting Grid Engine for %s @ %.2f (XTS + Zerodha/%s)",
                 args.symbol, anchor_price, args.user)
    engine = GridEngine(config)
    engine.start()


if __name__ == '__main__':
    main()
