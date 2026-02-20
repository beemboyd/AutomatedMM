"""
TollGate CLI Entry Point.

Usage:
    python -m TG.TollGate.run --auto-anchor
    python -m TG.TollGate.run --anchor 5.42
    python -m TG.TollGate.run --auto-anchor --dry-run
    python -m TG.TollGate.run --cancel-all
    python -m TG.TollGate.run --dashboard --mode monitor --port 7788
    python -m TG.TollGate.run --dashboard --mode config --port 7786
"""

import argparse
import sys
import os
import logging

# Ensure project root is on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description='TollGate — SPCENET Market-Making Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Anchor
    anchor_group = parser.add_mutually_exclusive_group()
    anchor_group.add_argument('--anchor', type=float, help='Grid anchor price')
    anchor_group.add_argument('--auto-anchor', action='store_true',
                              help='Auto-detect anchor from LTP')

    # Grid parameters
    parser.add_argument('--spacing', type=float, help='Base grid spacing (default: 0.01)')
    parser.add_argument('--profit', type=float, help='Round-trip profit target (default: 0.01)')
    parser.add_argument('--levels', type=int, help='Levels per side (default: 10)')
    parser.add_argument('--qty', type=int, help='Qty per level (default: 4000)')
    parser.add_argument('--product', choices=['NRML', 'MIS', 'CNC'], help='Product type')
    parser.add_argument('--poll-interval', type=float, help='Poll interval seconds')
    parser.add_argument('--max-reanchors', type=int, help='Max reanchors before stopping')
    parser.add_argument('--max-sub-depth', type=int, help='Max sub-target depth for partial fills (default: 5)')
    parser.add_argument('--amount', type=float, help='Fixed amount per level (overrides --qty)')
    parser.add_argument('--buy-amount', type=float, help='Buy side amount per level (overrides --amount for buys)')
    parser.add_argument('--sell-amount', type=float, help='Sell side amount per level (overrides --amount for sells)')
    parser.add_argument('--disclosed-pct', type=float, help='Disclosed qty percentage for iceberging (0-100)')

    # Credentials
    parser.add_argument('--interactive-key', type=str, help='XTS Interactive API key')
    parser.add_argument('--interactive-secret', type=str, help='XTS Interactive secret')
    parser.add_argument('--marketdata-key', type=str, help='XTS Market Data API key')
    parser.add_argument('--marketdata-secret', type=str, help='XTS Market Data secret')
    parser.add_argument('--xts-root', type=str, help='XTS root URL')

    # Actions
    parser.add_argument('--dry-run', action='store_true',
                        help='Print grid layout without placing orders')
    parser.add_argument('--cancel-all', action='store_true',
                        help='Cancel all open orders and exit')

    # Dashboard
    parser.add_argument('--dashboard', action='store_true',
                        help='Start web dashboard instead of trading engine')
    parser.add_argument('--mode', choices=['monitor', 'config'], default='monitor',
                        help='Dashboard mode (default: monitor)')
    parser.add_argument('--port', type=int, help='Dashboard port')
    parser.add_argument('--host', default='0.0.0.0', help='Dashboard bind host')

    # Logging
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level')

    args = parser.parse_args()

    # Configure logging
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'tollgate_engine.log')

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ]
    )
    logger = logging.getLogger(__name__)

    # Dashboard mode
    if args.dashboard:
        from .dashboard import create_app
        port = args.port or (7788 if args.mode == 'monitor' else 7786)
        logger.info("Starting TollGate Dashboard (%s) on %s:%d",
                     args.mode, args.host, port)
        app = create_app(mode=args.mode)
        app.run(host=args.host, port=port, debug=False)
        return

    # Build config
    from .config import TollGateConfig

    config = TollGateConfig()

    # Apply overrides
    if args.spacing is not None:
        config.base_spacing = args.spacing
    if args.profit is not None:
        config.round_trip_profit = args.profit
    if args.levels is not None:
        config.levels_per_side = args.levels
    if args.qty is not None:
        config.qty_per_level = args.qty
    if args.product:
        config.product = args.product
    if args.poll_interval is not None:
        config.poll_interval = args.poll_interval
    if args.max_reanchors is not None:
        config.max_reanchors = args.max_reanchors
    if args.max_sub_depth is not None:
        config.max_sub_depth = args.max_sub_depth
    if args.amount is not None:
        config.amount_per_level = args.amount
    if args.buy_amount is not None:
        config.buy_amount_per_level = args.buy_amount
    if args.sell_amount is not None:
        config.sell_amount_per_level = args.sell_amount
    if args.disclosed_pct is not None:
        config.disclosed_pct = args.disclosed_pct
    if args.interactive_key:
        config.interactive_key = args.interactive_key
    if args.interactive_secret:
        config.interactive_secret = args.interactive_secret
    if args.marketdata_key:
        config.marketdata_key = args.marketdata_key
    if args.marketdata_secret:
        config.marketdata_secret = args.marketdata_secret
    if args.xts_root:
        config.xts_root = args.xts_root

    # Resolve anchor
    if args.anchor:
        config.anchor_price = args.anchor
    elif args.auto_anchor:
        # Need to connect to get LTP
        if args.dry_run:
            logger.info("Dry run: auto-anchor not available without broker connection")
            config.anchor_price = 5.42  # Placeholder
            logger.info("Using placeholder anchor: %.2f", config.anchor_price)
        else:
            config.anchor_price = _resolve_auto_anchor(config)
            if config.anchor_price <= 0:
                logger.error("Failed to auto-detect anchor price")
                sys.exit(1)
    else:
        # Try to load from existing state
        from .state import TollGateState
        state = TollGateState(config.symbol)
        if state.load() and state.anchor_price > 0:
            config.anchor_price = state.anchor_price
            logger.info("Resumed anchor from state: %.2f", config.anchor_price)
        else:
            logger.error("No anchor specified. Use --anchor or --auto-anchor")
            sys.exit(1)

    # Dry run
    if args.dry_run:
        config.print_grid_layout()
        buy_levels, sell_levels = config.compute_levels()
        total_buy_qty = sum(lv.qty for lv in buy_levels)
        total_sell_qty = sum(lv.qty for lv in sell_levels)
        print(f"\n  Total buy exposure: {total_buy_qty} shares")
        print(f"  Total sell exposure: {total_sell_qty} shares")
        print(f"  Round-trip profit per cycle: {config.round_trip_profit}")
        if config.disclosed_pct > 0:
            print(f"  Disclosed qty: {config.disclosed_pct:.0f}% of order qty")
        print(f"  Dry run complete. No orders placed.\n")
        return

    # Cancel all
    if args.cancel_all:
        _cancel_all_orders(config)
        return

    # Initialize PnL tracker (fail-safe — None if DB unavailable)
    pnl_tracker = None
    try:
        from TG.pnl.tracker import PnLTracker
        pnl_tracker = PnLTracker()
        if pnl_tracker.available:
            logger.info("PnL tracker initialized")
        else:
            pnl_tracker = None
            logger.warning("PnL tracker unavailable — trading continues without tracking")
    except Exception as e:
        logger.warning("PnL tracker init failed (non-fatal): %s", e)

    # Start engine
    from .engine import TollGateEngine
    engine = TollGateEngine(config, pnl_tracker=pnl_tracker)
    engine.start()


def _resolve_auto_anchor(config) -> float:
    """
    Connect temporarily to get current market price for auto-anchoring.

    Uses full quote (bid/ask) to determine the true tradeable price,
    not just LTP which can be stale for illiquid instruments.
    If market has active bid/ask, the anchor is set to the mid-point.
    Falls back to LTP only if bid/ask is unavailable (e.g., pre-market).
    """
    from .client import TollGateClient
    _logger = logging.getLogger(__name__)

    client = TollGateClient(
        interactive_key=config.interactive_key,
        interactive_secret=config.interactive_secret,
        marketdata_key=config.marketdata_key,
        marketdata_secret=config.marketdata_secret,
        root_url=config.xts_root,
    )
    if not client.connect():
        return 0.0

    try:
        quote = client.get_quote(config.symbol, config.exchange)
        if not quote:
            _logger.warning("Quote unavailable, falling back to LTP")
            ltp = client.get_ltp(config.symbol, config.exchange)
            if ltp and ltp > 0:
                anchor = round(ltp, 2)
                _logger.info("Auto-anchor (LTP fallback): %.2f", anchor)
                return anchor
            return 0.0

        ltp = quote['ltp']
        best_bid = quote['best_bid']
        best_ask = quote['best_ask']
        _logger.info("Auto-anchor quote: LTP=%.2f, Bid=%.2f, Ask=%.2f",
                      ltp, best_bid, best_ask)

        # Use bid/ask mid-point if both are available and valid
        if best_bid > 0 and best_ask > 0:
            mid = round((best_bid + best_ask) / 2, 2)
            spread = best_ask - best_bid
            _logger.info("Auto-anchor: using bid/ask mid=%.2f (spread=%.2f)", mid, spread)

            if ltp > 0 and abs(ltp - mid) > spread * 2:
                _logger.warning("LTP %.2f is far from bid/ask mid %.2f — "
                                "LTP appears stale, using mid-point instead", ltp, mid)
            return mid

        if ltp and ltp > 0:
            anchor = round(ltp, 2)
            _logger.info("Auto-anchor (no bid/ask): LTP=%.2f", anchor)
            return anchor

        return 0.0
    finally:
        client.stop()


def _cancel_all_orders(config):
    """Connect and cancel all open orders."""
    from .client import TollGateClient
    from .engine import TollGateEngine

    client = TollGateClient(
        interactive_key=config.interactive_key,
        interactive_secret=config.interactive_secret,
        marketdata_key=config.marketdata_key,
        marketdata_secret=config.marketdata_secret,
        root_url=config.xts_root,
    )
    if not client.connect():
        logging.getLogger(__name__).error("Cannot connect to cancel orders")
        return

    try:
        engine = TollGateEngine(config)
        engine.client = client
        engine.state.load()
        engine._rebuild_level_groups()
        engine.cancel_all()
        logging.getLogger(__name__).info("All orders cancelled")
    finally:
        client.stop()


if __name__ == '__main__':
    main()
