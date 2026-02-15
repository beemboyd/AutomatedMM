#!/usr/bin/env python
"""
TG1 — Grid OCO Trading Bot Entry Point.

Two-token grid trading with OCO hedging via Findoc XTS + Zerodha WebSocket.

Usage:
    # Bidirectional grid with OCO (gridocots)
    python -m TG1.run --bot-name "IRFC-SBIN Grid" \\
        --trade-type gridocots \\
        --token-a IRFC --token-b SBIN \\
        --entry-price 50.00 --steps 5 --spread 1.0 \\
        --target-spread 0.50 --oco-spread 2.0 \\
        --qty-a 100 --qty-b 50 \\
        --trade-key KEY --trade-secret SECRET \\
        --upside-oco-key KEY2 --upside-oco-secret SECRET2 \\
        --downside-oco-key KEY3 --downside-oco-secret SECRET3

    # Buy-only grid with OCO
    python -m TG1.run --bot-name "IRFC Buy OCO" \\
        --trade-type buyocots \\
        --token-a IRFC --token-b SBIN \\
        --entry-price 50.00 --steps 3 --spread 0.50 \\
        --target-spread 0.25 --oco-spread 1.0 \\
        --qty-a 100 --qty-b 50 \\
        --trade-key KEY --trade-secret SECRET \\
        --upside-oco-key KEY2 --upside-oco-secret SECRET2 \\
        --downside-oco-key KEY3 --downside-oco-secret SECRET3

    # Buy-only grid without OCO (buyts)
    python -m TG1.run --bot-name "IRFC Buy Grid" \\
        --trade-type buyts \\
        --token-a IRFC --entry-price 50.00 \\
        --steps 5 --spread 0.50 --target-spread 0.25 \\
        --qty-a 100 \\
        --trade-key KEY --trade-secret SECRET

    # Dry run (print grid layout only)
    python -m TG1.run --bot-name "Test" --trade-type gridocots \\
        --token-a IRFC --token-b SBIN \\
        --entry-price 50.00 --steps 5 --spread 1.0 \\
        --target-spread 0.50 --oco-spread 2.0 \\
        --qty-a 100 --qty-b 50 --dry-run

    # Cancel all open orders
    python -m TG1.run --bot-name "IRFC-SBIN Grid" --cancel-all \\
        --trade-key KEY --trade-secret SECRET \\
        --upside-oco-key KEY2 --upside-oco-secret SECRET2 \\
        --downside-oco-key KEY3 --downside-oco-secret SECRET3
"""

import sys
import os
import argparse
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from TG1.config import GridOcoConfig, _DEFAULT_XTS_ROOT
from TG1.grid_engine import GridOcoEngine


def setup_logging(log_level: str = "INFO"):
    """Configure logging to console and file."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'grid_oco_engine.log')

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
        description='TG1 — Grid OCO Trading Bot (XTS + Zerodha WebSocket)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Bot identity
    parser.add_argument('--bot-name', required=True,
                        help='Unique bot name (used for state file)')
    parser.add_argument('--trade-type', default='gridocots',
                        choices=['gridocots', 'buyocots', 'sellocots',
                                 'buyts', 'sellts'],
                        help='Trade type (default: gridocots)')

    # Instruments
    parser.add_argument('--token-a', required=True,
                        help='TokenA trading symbol (grid-traded, e.g., IRFC)')
    parser.add_argument('--token-b', default='',
                        help='TokenB trading symbol (OCO hedge, e.g., SBIN)')

    # Grid parameters
    parser.add_argument('--entry-price', type=float, default=0.0,
                        help='Grid center price')
    parser.add_argument('--auto-entry', action='store_true',
                        help='Use current LTP of TokenA as entry price')
    parser.add_argument('--steps', type=int, default=5,
                        help='Number of grid levels per side (default: 5)')
    parser.add_argument('--spread', type=float, default=1.0,
                        help='Entry spacing between grid levels (default: 1.0)')
    parser.add_argument('--target-spread', type=float, default=0.5,
                        help='Target offset from entry price (default: 0.5)')
    parser.add_argument('--oco-spread', type=float, default=0.0,
                        help='OCO offset from TokenB price (default: 0)')
    parser.add_argument('--qty-a', type=int, default=0,
                        help='TokenA quantity per grid level')
    parser.add_argument('--qty-b', type=int, default=0,
                        help='TokenB quantity per OCO order')

    # Broker parameters
    parser.add_argument('--exchange', default='NSE',
                        help='Exchange (default: NSE)')
    parser.add_argument('--product', default='MIS',
                        choices=['MIS', 'CNC', 'NRML'],
                        help='Product type (default: MIS)')

    # Termination
    parser.add_argument('--oco-stop-count', type=int, default=3,
                        help='Terminate if untriggered OCO count >= this (default: 3)')

    # XTS credentials — Trade Account
    parser.add_argument('--trade-key', default='',
                        help='XTS API key for Trade account')
    parser.add_argument('--trade-secret', default='',
                        help='XTS API secret for Trade account')

    # XTS credentials — Upside OCO Account
    parser.add_argument('--upside-oco-key', default='',
                        help='XTS API key for Upside OCO account')
    parser.add_argument('--upside-oco-secret', default='',
                        help='XTS API secret for Upside OCO account')

    # XTS credentials — Downside OCO Account
    parser.add_argument('--downside-oco-key', default='',
                        help='XTS API key for Downside OCO account')
    parser.add_argument('--downside-oco-secret', default='',
                        help='XTS API secret for Downside OCO account')

    # Zerodha
    parser.add_argument('--user', default='Sai',
                        help='Zerodha user for market data (default: Sai)')

    # XTS root
    parser.add_argument('--xts-root', default=_DEFAULT_XTS_ROOT,
                        help=f'XTS API root URL (default: {_DEFAULT_XTS_ROOT})')

    # Operational
    parser.add_argument('--poll-interval', type=float, default=1.0,
                        help='Poll interval in seconds (default: 1.0)')
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
    logger = logging.getLogger('TG1')

    # Build config
    config = GridOcoConfig(
        bot_name=args.bot_name,
        trade_type=args.trade_type,
        token_a_symbol=args.token_a.upper(),
        token_b_symbol=args.token_b.upper() if args.token_b else '',
        entry_price=args.entry_price,
        steps=args.steps,
        spread=args.spread,
        target_spread=args.target_spread,
        oco_spread=args.oco_spread,
        token_a_quantity=args.qty_a,
        token_b_quantity=args.qty_b,
        product_type=args.product,
        exchange=args.exchange,
        oco_stop_count=args.oco_stop_count,
        trade_key=args.trade_key,
        trade_secret=args.trade_secret,
        upside_oco_key=args.upside_oco_key,
        upside_oco_secret=args.upside_oco_secret,
        downside_oco_key=args.downside_oco_key,
        downside_oco_secret=args.downside_oco_secret,
        zerodha_user=args.user,
        xts_root=args.xts_root,
        poll_interval=args.poll_interval,
        auto_reenter=not args.no_reenter,
    )

    # Dry run: just print grid and exit
    if args.dry_run:
        config.print_grid_layout()
        print(f"  Max Quantity      : {config.max_quantity}")
        print(f"  Has OCO           : {config.has_oco}")
        if config.has_oco:
            same = "YES (shared)" if config.same_oco_account else "NO (separate)"
            print(f"  Same OCO Account  : {same}")
        print(f"\n  This is a dry run. No orders placed.\n")
        return

    # Auto-entry: fetch LTP
    if args.auto_entry:
        from TG1.findoc_client import _load_zerodha_credentials
        from kiteconnect import KiteConnect
        logger.info("Fetching LTP for %s from Zerodha (user=%s)...",
                     config.token_a_symbol, config.zerodha_user)
        try:
            creds = _load_zerodha_credentials(config.zerodha_user)
            kite = KiteConnect(api_key=creds['api_key'])
            kite.set_access_token(creds['access_token'])
            key = f"{config.exchange}:{config.token_a_symbol}"
            data = kite.ltp([key])
            ltp = data[key]['last_price']
            config.entry_price = ltp
            logger.info("Auto-entry: %s LTP = %.2f",
                         config.token_a_symbol, ltp)
        except Exception as e:
            logger.error("Auto-entry failed: %s", e)
            sys.exit(1)

    # Validate config (skip some checks for cancel-all)
    if not args.cancel_all:
        try:
            config.validate()
        except ValueError as e:
            logger.error("Invalid config: %s", e)
            sys.exit(1)

    # Cancel all orders
    if args.cancel_all:
        engine = GridOcoEngine(config)
        if not engine.client.connect():
            logger.error("Cannot connect to cancel orders")
            sys.exit(1)
        if engine.state.load():
            engine.cancel_all()
            logger.info("All orders cancelled.")
        else:
            logger.info("No saved state found. Nothing to cancel.")
        return

    # Start the engine
    logger.info("Starting TG1 Grid OCO Engine: %s (%s)",
                 config.bot_name, config.trade_type)
    engine = GridOcoEngine(config)
    engine.start()


if __name__ == '__main__':
    main()
