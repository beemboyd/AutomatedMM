"""
Simulation 5: Long Daily + KC Lower SL
VSR Trading Simulation

Strategy:
- Direction: LONG positions only
- Timeframe: DAILY (vs Hourly for sim_1)
- Entry: VSR Long Daily signals from FNO/Long/Liquid
- Stop Loss: Fixed at Keltner Channel Lower band (Daily)
- Charges: 0.15% per leg
- Can hold overnight: Yes
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from runners.base_runner import BaseSimulationRunner
from core.keltner_calculator import get_kc_calculator

logger = logging.getLogger(__name__)


class Simulation5Runner(BaseSimulationRunner):
    """
    Simulation 5: Long Daily + KC Lower SL

    - Long positions on DAILY timeframe with fixed Stop Loss at Keltner Channel Lower band
    - Signals from Long Reversal Daily scans (FNO/Long/Liquid)
    - Charges: 0.15% per leg (0.30% round trip)
    - Can hold overnight
    """

    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        super().__init__('sim_5', config)

        logger.info(f"Simulation 5 initialized: LONG DAILY + KC Lower SL")

    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """
        Entry logic for Simulation 5 (Long Daily + KC Lower)
        """
        # Base validation
        can_enter, reason = super().should_enter(signal)
        if not can_enter:
            return False, reason

        # Additional filters for Long positions can be added here
        # Example: liquidity grade filter, sector filter, etc.

        return True, "OK"

    def _get_stop_loss(self, kc_data: Dict, entry_price: float) -> float:
        """
        Stop loss at Keltner Channel Lower
        """
        return kc_data.get('lower', entry_price * 0.95)


def main():
    """Run Simulation 5"""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'simulation_5.log'),
            logging.StreamHandler()
        ]
    )

    runner = Simulation5Runner()

    import argparse
    parser = argparse.ArgumentParser(description='Simulation 5: Long Daily + KC Lower SL')
    parser.add_argument('--once', action='store_true', help='Run single iteration')
    parser.add_argument('--eod', action='store_true', help='Run end of day processing')
    parser.add_argument('--reset', action='store_true', help='Reset simulation')
    args = parser.parse_args()

    if args.reset:
        runner.reset()
        print("Simulation 5 reset complete")
    elif args.eod:
        runner.end_of_day()
    elif args.once:
        runner.run_once()
    else:
        runner.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runner.stop()


if __name__ == '__main__':
    main()
