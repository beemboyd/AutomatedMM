"""
Simulation 3: Short + KC Upper SL
VSR Trading Simulation

Strategy:
- Direction: SHORT positions only (Intraday)
- Entry: VSR Short signals from dashboard (localhost:3003)
- Stop Loss: Fixed at Keltner Channel Upper band (Daily)
- Charges: 0.035% per leg
- Can hold overnight: NO - All positions closed at EOD (3:15 PM)
"""

import json
import logging
import sys
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from runners.base_runner import BaseSimulationRunner
from core.keltner_calculator import get_kc_calculator

logger = logging.getLogger(__name__)


class Simulation3Runner(BaseSimulationRunner):
    """
    Simulation 3: Short + KC Upper SL (Intraday Only)

    - Short positions with fixed Stop Loss at Keltner Channel Upper band
    - Signals from VSR Short tracker (port 3003)
    - Charges: 0.035% per leg (0.07% round trip)
    - CANNOT hold overnight - mandatory EOD close at 3:15 PM
    - No new entries after 3:00 PM
    """

    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        super().__init__('sim_3', config)

        logger.info(f"Simulation 3 initialized: SHORT + KC Upper SL (Intraday)")

    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """
        Entry logic for Simulation 3 (Short + KC Upper)
        """
        can_enter, reason = super().should_enter(signal)
        if not can_enter:
            return False, reason

        # No short entries after 3 PM
        now = datetime.now().time()
        if now >= dt_time(15, 0):
            return False, "No short entries after 3:00 PM"

        return True, "OK"

    def _get_stop_loss(self, kc_data: Dict, entry_price: float) -> float:
        """
        Stop loss at Keltner Channel Upper for shorts
        """
        return kc_data.get('upper', entry_price * 1.05)

    def update_prices_and_check_exits(self, prices: Dict[str, float]):
        """Override to include EOD check for shorts"""
        if not prices:
            return

        # Check EOD close first (mandatory for shorts)
        self.check_eod_close(prices)

        # Then normal price updates and stop checks
        super().update_prices_and_check_exits(prices)


def main():
    """Run Simulation 3"""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'simulation_3.log'),
            logging.StreamHandler()
        ]
    )

    runner = Simulation3Runner()

    import argparse
    parser = argparse.ArgumentParser(description='Simulation 3: Short + KC Upper SL (Intraday)')
    parser.add_argument('--once', action='store_true', help='Run single iteration')
    parser.add_argument('--eod', action='store_true', help='Run end of day processing')
    parser.add_argument('--reset', action='store_true', help='Reset simulation')
    args = parser.parse_args()

    if args.reset:
        runner.reset()
        print("Simulation 3 reset complete")
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
