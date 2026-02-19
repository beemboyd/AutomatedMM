"""
AMM CLI Entry Point.

Usage:
    python -m TG.AMM.run                          # Start engine with defaults
    python -m TG.AMM.run --config-file path.json  # Load config from file
    python -m TG.AMM.run --dry-run                # Print config and exit
    python -m TG.AMM.run --dashboard --mode monitor --port 7797
    python -m TG.AMM.run --dashboard --mode config --port 7796
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
        description='AMM — Ratio Mean-Reversion Stat-Arb Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Config file
    parser.add_argument('--config-file', type=str,
                        help='Load full config from JSON file')

    # Parameter overrides
    parser.add_argument('--base-qty', type=int, help='Base quantity reference')
    parser.add_argument('--rolling-window', type=int, help='Rolling window for mean/SD')
    parser.add_argument('--sample-interval', type=int, help='Seconds between ratio samples')
    parser.add_argument('--product', choices=['CNC', 'MIS', 'NRML'], help='Product type')
    parser.add_argument('--max-positions', type=int, help='Max positions per pair')
    parser.add_argument('--mean-reversion-tolerance', type=float,
                        help='Mean reversion exit tolerance')
    parser.add_argument('--slippage', type=float, help='Aggressive limit offset')
    parser.add_argument('--poll-interval', type=float, help='Order poll interval seconds')
    parser.add_argument('--warmup-samples', type=int, help='Min samples before trading')

    # Credentials
    parser.add_argument('--interactive-key', type=str, help='XTS Interactive API key')
    parser.add_argument('--interactive-secret', type=str, help='XTS Interactive secret')
    parser.add_argument('--marketdata-key', type=str, help='XTS Market Data API key')
    parser.add_argument('--marketdata-secret', type=str, help='XTS Market Data secret')
    parser.add_argument('--xts-root', type=str, help='XTS root URL')

    # Actions
    parser.add_argument('--dry-run', action='store_true',
                        help='Print config summary and exit')

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
    log_file = os.path.join(log_dir, 'amm_engine.log')

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
        port = args.port or (7797 if args.mode == 'monitor' else 7796)
        logger.info("Starting AMM Dashboard (%s) on %s:%d",
                     args.mode, args.host, port)
        app = create_app(mode=args.mode)
        app.run(host=args.host, port=port, debug=False)
        return

    # Build config
    from .config import AMMConfig

    if args.config_file:
        config = AMMConfig.load_from_file(args.config_file)
        logger.info("Loaded config from %s", args.config_file)
    else:
        config = AMMConfig.load_from_file()  # Try default location, fallback to defaults

    # Apply CLI overrides
    if args.base_qty is not None:
        config.base_qty = args.base_qty
    if args.rolling_window is not None:
        config.rolling_window = args.rolling_window
    if args.sample_interval is not None:
        config.sample_interval = args.sample_interval
    if args.product:
        config.product = args.product
    if args.max_positions is not None:
        config.max_positions_per_pair = args.max_positions
    if args.mean_reversion_tolerance is not None:
        config.mean_reversion_tolerance = args.mean_reversion_tolerance
    if args.slippage is not None:
        config.slippage = args.slippage
    if args.poll_interval is not None:
        config.poll_interval = args.poll_interval
    if args.warmup_samples is not None:
        config.warmup_samples = args.warmup_samples
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

    # Dry run
    if args.dry_run:
        config.print_summary()
        print("  Dry run complete. No trading.\n")
        return

    # Initialize PnL tracker (fail-safe)
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
    from .engine import AMMEngine
    engine = AMMEngine(config, pnl_tracker=pnl_tracker)
    engine.start()


if __name__ == '__main__':
    main()
