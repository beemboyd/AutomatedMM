"""
Simulation 4: Short + PSAR Dynamic SL
VSR Trading Simulation

Strategy:
- Direction: SHORT positions only (Intraday)
- Entry: VSR Short signals from dashboard (localhost:3003)
- Stop Loss: Dynamic trailing using Parabolic SAR
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
from core.psar_calculator import get_psar_calculator

logger = logging.getLogger(__name__)


class Simulation4Runner(BaseSimulationRunner):
    """
    Simulation 4: Short + PSAR Dynamic SL (Intraday Only)

    - Short positions with dynamic trailing Stop Loss using Parabolic SAR
    - Signals from VSR Short tracker (port 3003)
    - Charges: 0.035% per leg (0.07% round trip)
    - CANNOT hold overnight - mandatory EOD close at 3:15 PM
    - No new entries after 3:00 PM
    - PSAR trail updates on each price check
    """

    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        super().__init__('sim_4', config)

        # Initialize PSAR calculator
        psar_config = config.get('psar', {})
        self.psar_calculator = get_psar_calculator(
            af_start=psar_config.get('af_start', 0.02),
            af_increment=psar_config.get('af_increment', 0.02),
            af_max=psar_config.get('af_max', 0.2)
        )

        logger.info(f"Simulation 4 initialized: SHORT + PSAR Dynamic SL (Intraday)")

    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """
        Entry logic for Simulation 4 (Short + PSAR)
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
        Initial stop loss at KC Upper, then trail with PSAR
        """
        return kc_data.get('upper', entry_price * 1.05)

    def update_psar_trailing_stops(self):
        """
        Update trailing stops for all positions using PSAR
        For shorts, we trail DOWN when in downtrend
        """
        for ticker, position in self.portfolio.positions.items():
            try:
                psar_data = self.psar_calculator.get_psar_values(ticker, 'day', use_cache=False)
                if psar_data and psar_data['trend'] == -1:  # Only trail in downtrend for shorts
                    new_stop = psar_data['psar']
                    self.update_trailing_stop(ticker, new_stop)
            except Exception as e:
                logger.warning(f"Error updating PSAR stop for {ticker}: {e}")

    def update_prices_and_check_exits(self, prices: Dict[str, float]):
        """Override to include EOD check and PSAR trailing for shorts"""
        if not prices:
            return

        # Check EOD close first (mandatory for shorts)
        self.check_eod_close(prices)

        # Then normal price updates and stop checks
        super().update_prices_and_check_exits(prices)

    def _price_update_loop(self, interval: int = 60):
        """Override to include PSAR trailing stop updates and EOD check"""
        while not self._stop_event.is_set():
            try:
                if self.portfolio.positions:
                    # Update PSAR trailing stops
                    self.update_psar_trailing_stops()

                    # Then check stops and prices (includes EOD check)
                    prices = self._fetch_current_prices()
                    if prices:
                        self.update_prices_and_check_exits(prices)
            except Exception as e:
                logger.error(f"Error in price update loop: {e}")

            self._stop_event.wait(interval)


def main():
    """Run Simulation 4"""
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'simulation_4.log'),
            logging.StreamHandler()
        ]
    )

    runner = Simulation4Runner()

    import argparse
    parser = argparse.ArgumentParser(description='Simulation 4: Short + PSAR Dynamic SL (Intraday)')
    parser.add_argument('--once', action='store_true', help='Run single iteration')
    parser.add_argument('--eod', action='store_true', help='Run end of day processing')
    parser.add_argument('--reset', action='store_true', help='Reset simulation')
    args = parser.parse_args()

    if args.reset:
        runner.reset()
        print("Simulation 4 reset complete")
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
