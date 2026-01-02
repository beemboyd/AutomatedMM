"""
Simulation 5: TickFlow 1K + MA2 Crossover Exit
VSR Trading Simulation

Strategy:
- Direction: LONG positions only
- Entry Source: TickFlow 1K tick section (port 6063) - RED>0 & WM>0 & WM>9EMA(WM)
- Exit: TD MA2 Fast (3-SMA) closes below TD MA2 Slow (34-SMA)
- Trading Start: 9:30 AM on weekdays
- Charges: 0.10% per leg
- Can hold overnight: Yes
"""

import json
import logging
import sys
import time
import requests
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, Tuple, Optional
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from runners.base_runner import BaseSimulationRunner
from core.signal_listener import get_signal_listener, VSRSignal
from core.td_indicators import TDIndicatorCalculator

logger = logging.getLogger(__name__)


class Simulation5Runner(BaseSimulationRunner):
    """
    Simulation 5: TickFlow 1K + MA2 Crossover Exit

    - Long positions from TickFlow 1K tick section (RED>0 & WM>0)
    - Exit when TD MA2 Fast (3-SMA) closes below TD MA2 Slow (34-SMA)
    - Starts trading at 9:30 AM on weekdays
    - Charges: 0.10% per leg (0.20% round trip)
    - Can hold overnight
    """

    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        super().__init__('sim_5', config)

        # TD Indicator calculator for MA2 crossover exit
        self.td_calculator = TDIndicatorCalculator()

        # Trading start time (9:30 AM)
        self.trading_start_time = dt_time(9, 30)

        # Cache for MA2 data per ticker
        self._ma2_cache = {}
        self._ma2_cache_time = {}
        self._ma2_cache_ttl = 300  # 5 minutes cache

        logger.info(f"Simulation 5 initialized: TickFlow 1K + MA2 Crossover Exit (starts 9:30 AM)")

    def _is_trading_time(self) -> bool:
        """Check if current time is within trading hours (after 9:30 AM on weekdays)"""
        now = datetime.now()

        # Check if weekday (0=Monday, 6=Sunday)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False

        # Check if after 9:30 AM
        current_time = now.time()
        if current_time < self.trading_start_time:
            return False

        # Check if before market close (3:30 PM)
        market_close = dt_time(15, 30)
        if current_time > market_close:
            return False

        return True

    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """
        Entry logic for Simulation 5 (TickFlow 1K + MA2 Crossover)
        """
        # Check if it's trading time (after 9:30 AM on weekdays)
        if not self._is_trading_time():
            current_time = datetime.now().strftime('%H:%M')
            return False, f"Outside trading hours (current: {current_time}, start: 09:30)"

        # Base validation
        can_enter, reason = super().should_enter(signal)
        if not can_enter:
            return False, reason

        # Additional filter: Check if MA2 Fast > MA2 Slow (confirm uptrend)
        ticker = signal.get('ticker', '')
        if ticker:
            ma2_data = self._get_ma2_data(ticker)
            if ma2_data:
                ma2_fast = ma2_data.get('ma2_fast', 0)
                ma2_slow = ma2_data.get('ma2_slow', 0)
                if ma2_fast <= ma2_slow:
                    return False, f"MA2 Fast ({ma2_fast:.2f}) <= MA2 Slow ({ma2_slow:.2f})"

        return True, "OK"

    def _get_stop_loss(self, kc_data: Dict, entry_price: float) -> float:
        """
        Stop loss at Keltner Channel Lower (initial protection)
        Will be overridden by MA2 crossover exit logic
        """
        return kc_data.get('lower', entry_price * 0.95)

    def _init_kite(self):
        """Initialize Kite connection"""
        if not hasattr(self, '_kite') or self._kite is None:
            import configparser
            from kiteconnect import KiteConnect

            config = configparser.ConfigParser()
            config_path = Path(__file__).parent.parent.parent / 'config.ini'
            config.read(config_path)

            api_key = config.get('API_CREDENTIALS_Sai', 'api_key')
            access_token = config.get('API_CREDENTIALS_Sai', 'access_token')

            self._kite = KiteConnect(api_key=api_key)
            self._kite.set_access_token(access_token)
            logger.info("Kite connection initialized for Simulation 5")

    def _get_ma2_data(self, ticker: str) -> Optional[Dict]:
        """
        Get TD MA2 Fast/Slow data for a ticker

        Uses daily OHLC data to calculate:
        - MA2 Fast: 3-SMA of closes
        - MA2 Slow: 34-SMA of closes
        """
        try:
            # Check cache
            now = time.time()
            if ticker in self._ma2_cache:
                cache_age = now - self._ma2_cache_time.get(ticker, 0)
                if cache_age < self._ma2_cache_ttl:
                    return self._ma2_cache[ticker]

            # Initialize Kite if needed
            self._init_kite()

            # Get instrument token
            instrument_token = self._get_instrument_token(ticker)
            if not instrument_token:
                return None

            # Fetch historical data (need at least 40 days for 34-SMA)
            from_date = datetime.now() - pd.Timedelta(days=60)
            to_date = datetime.now()

            data = self._kite.historical_data(
                instrument_token=instrument_token,
                from_date=from_date,
                to_date=to_date,
                interval='day'
            )

            if not data or len(data) < 35:
                logger.warning(f"Insufficient data for {ticker}: {len(data) if data else 0} bars")
                return None

            df = pd.DataFrame(data)

            # Calculate MA2 crossover indicators
            df = self.td_calculator.calculate_ma2_crossover(df)

            # Get latest values
            last_row = df.iloc[-1]
            result = {
                'ma2_fast': float(last_row.get('ma2_fast', 0)),
                'ma2_slow': float(last_row.get('ma2_slow', 0)),
                'ma2_fast_below_slow': bool(last_row.get('ma2_fast_below_slow', False)),
                'ma2_entry_valid': bool(last_row.get('ma2_entry_valid', False)),
                'close': float(last_row.get('close', 0))
            }

            # Update cache
            self._ma2_cache[ticker] = result
            self._ma2_cache_time[ticker] = now

            return result

        except Exception as e:
            logger.error(f"Error getting MA2 data for {ticker}: {e}")
            return None

    def _get_instrument_token(self, ticker: str) -> Optional[int]:
        """Get instrument token for a ticker"""
        try:
            self._init_kite()

            if not hasattr(self, '_instruments'):
                self._instruments = self._kite.instruments('NSE')

            for inst in self._instruments:
                if inst['tradingsymbol'] == ticker:
                    return inst['instrument_token']

            return None
        except Exception as e:
            logger.error(f"Error getting instrument token for {ticker}: {e}")
            return None

    def check_ma2_exit(self, ticker: str) -> Tuple[bool, str]:
        """
        Check if MA2 crossover exit condition is met

        Exit when: TD MA2 Fast (3-SMA) closes below TD MA2 Slow (34-SMA)
        """
        ma2_data = self._get_ma2_data(ticker)
        if not ma2_data:
            return False, "No MA2 data"

        if ma2_data.get('ma2_fast_below_slow', False):
            ma2_fast = ma2_data.get('ma2_fast', 0)
            ma2_slow = ma2_data.get('ma2_slow', 0)
            return True, f"MA2 Fast ({ma2_fast:.2f}) < MA2 Slow ({ma2_slow:.2f})"

        return False, ""

    def process_exits(self) -> None:
        """Override to check MA2 crossover exits in addition to stop loss/target"""
        # First check regular stop losses and targets
        super().process_exits()

        # Then check MA2 crossover exits for remaining positions
        for ticker in list(self.engine.portfolio.positions.keys()):
            should_exit, reason = self.check_ma2_exit(ticker)
            if should_exit:
                logger.info(f"MA2 Exit triggered for {ticker}: {reason}")
                self.engine.close_position(ticker, reason=f"MA2_CROSSOVER: {reason}")


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
    parser = argparse.ArgumentParser(description='Simulation 5: TickFlow 1K + MA2 Crossover Exit')
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
