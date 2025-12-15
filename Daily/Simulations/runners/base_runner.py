"""
Base Simulation Runner
Template for VSR simulation runners - extend this for specific simulation logic
"""

import json
import logging
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Tuple, Optional
from threading import Thread, Event

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_manager import SimulationDatabase
from core.simulation_engine import BaseSimulationEngine, Portfolio, Position
from core.keltner_calculator import get_kc_calculator
from core.signal_listener import VSRSignal, get_signal_listener

logger = logging.getLogger(__name__)


class BaseSimulationRunner(BaseSimulationEngine):
    """
    Base runner for VSR simulations
    Extend this class to implement specific entry/exit logic
    """

    def __init__(self, sim_id: str, config: Dict = None):
        if config is None:
            config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
            with open(config_path, 'r') as f:
                config = json.load(f)

        super().__init__(sim_id, config)

        # Initialize components
        kc_config = config.get('keltner_channel', {})
        self.kc_calculator = get_kc_calculator(
            ema_period=kc_config.get('ema_period', 20),
            atr_period=kc_config.get('atr_period', 10),
            atr_multiplier=kc_config.get('atr_multiplier', 2.0)
        )

        # Get signal listener based on direction (long vs short) with sim_id for config lookup
        signal_type = self.direction  # 'long' or 'short' from simulation_engine
        self.signal_listener = get_signal_listener(config, signal_type=signal_type, sim_id=sim_id)

        # Running state
        self._stop_event = Event()
        self._runner_thread = None
        self._price_update_thread = None

        # Register signal callback
        self.signal_listener.register_callback(self._on_signal)

    def _on_signal(self, signal: VSRSignal):
        """Callback when a new VSR signal arrives"""
        logger.info(f"Received signal: {signal.ticker} @ {signal.price} (Score: {signal.vsr_score}, Mom: {signal.vsr_momentum})")
        self.process_signal(signal.to_dict())

    def process_signal(self, signal: Dict) -> bool:
        """
        Process an incoming VSR signal
        Override should_enter() for custom entry logic
        """
        ticker = signal.get('ticker')
        if not ticker:
            return False

        # Check if we should enter
        should_enter, reason = self.should_enter(signal)
        if not should_enter:
            logger.info(f"Signal rejected for {ticker}: {reason}")
            self.db.log_signal(
                ticker=ticker,
                timestamp=signal.get('timestamp', datetime.now().isoformat()),
                price=signal.get('price'),
                vsr_score=signal.get('vsr_score'),
                vsr_momentum=signal.get('vsr_momentum'),
                pattern=signal.get('pattern'),
                action_taken='REJECTED',
                rejection_reason=reason
            )
            return False

        # Get Keltner Channel data for stop loss
        kc_data = self.kc_calculator.get_kc_values(ticker)
        if kc_data is None:
            logger.warning(f"Could not get KC data for {ticker}, using default SL")
            signal_price = signal.get('price', 0)
            kc_data = {
                'lower': signal_price * 0.95,
                'upper': signal_price * 1.05,
                'middle': signal_price,
                'atr': signal_price * 0.02
            }

        # Open position
        trade_id = self.open_position(
            ticker=ticker,
            signal_price=signal.get('price'),
            entry_price=signal.get('price'),  # TODO: Can add slippage simulation
            kc_data=kc_data,
            vsr_score=signal.get('vsr_score'),
            vsr_momentum=signal.get('vsr_momentum'),
            signal_pattern=signal.get('pattern'),
            metadata=signal.get('metadata')
        )

        return trade_id is not None

    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """
        Default entry logic - override in subclasses for specific strategies
        Base implementation: accept all signals that pass basic filters
        """
        ticker = signal.get('ticker')

        # Check if already have position
        if ticker in self.portfolio.positions:
            return False, "Already have position"

        # Check max positions
        if self.portfolio.open_position_count >= self.max_positions:
            return False, "Max positions reached"

        # Check minimum score - use entry_filter from simulation config
        entry_filter = self.sim_config.get('entry_filter', {})
        # For shorts (X/11 scoring), default to 50%. For longs (X/7), default to 70%
        default_min_score = 70 if self.direction == 'long' else 50
        min_score = entry_filter.get('min_score', default_min_score)
        if signal.get('vsr_score', 0) < min_score:
            return False, f"Score {signal.get('vsr_score')} below minimum {min_score}"

        # Check minimum momentum
        # For longs: we want positive momentum (bullish), default to 3.0
        # For shorts: negative momentum is expected (bearish), so we skip momentum check or use very negative threshold
        default_min_momentum = 3.0 if self.direction == 'long' else -100.0
        min_momentum = entry_filter.get('min_momentum', default_min_momentum)
        if signal.get('vsr_momentum', 0) < min_momentum:
            return False, f"Momentum {signal.get('vsr_momentum')} below minimum {min_momentum}"

        return True, "OK"

    def update_prices_and_check_exits(self, prices: Dict[str, float]):
        """Update position prices and check for stop losses/targets"""
        if not prices:
            return

        # Update prices
        self.update_position_prices(prices)

        # Check stop losses
        stopped = self.check_stop_losses(prices)
        for ticker in stopped:
            logger.info(f"Stop loss triggered for {ticker}")

        # Check targets (optional)
        targets_hit = self.check_targets(prices)
        for ticker in targets_hit:
            logger.info(f"Target hit for {ticker}")

    def _fetch_current_prices(self) -> Dict[str, float]:
        """Fetch current prices for all open positions"""
        if not self.portfolio.positions:
            return {}

        try:
            self.kc_calculator._init_kite()
            tickers = list(self.portfolio.positions.keys())
            symbols = [f"NSE:{t}" for t in tickers]

            ltp_data = self.kc_calculator.kite.ltp(symbols)

            prices = {}
            for symbol, data in ltp_data.items():
                ticker = symbol.replace("NSE:", "")
                prices[ticker] = data.get('last_price', 0)

            return prices

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {}

    def _price_update_loop(self, interval: int = 60):
        """Background loop to update prices and check exits"""
        while not self._stop_event.is_set():
            try:
                if self.portfolio.positions:
                    prices = self._fetch_current_prices()
                    if prices:
                        self.update_prices_and_check_exits(prices)
            except Exception as e:
                logger.error(f"Error in price update loop: {e}")

            self._stop_event.wait(interval)

    def start(self, signal_poll_interval: int = 60, price_update_interval: int = 60):
        """Start the simulation runner"""
        logger.info(f"Starting simulation {self.sim_id}")

        # Start signal listener
        self.signal_listener.start_listening(signal_poll_interval)

        # Start price update thread
        self._stop_event.clear()
        self._price_update_thread = Thread(
            target=self._price_update_loop,
            args=(price_update_interval,),
            daemon=True
        )
        self._price_update_thread.start()

        logger.info(f"Simulation {self.sim_id} running")

    def stop(self):
        """Stop the simulation runner"""
        logger.info(f"Stopping simulation {self.sim_id}")

        self._stop_event.set()
        self.signal_listener.stop_listening()

        if self._price_update_thread:
            self._price_update_thread.join(timeout=5)

        # Save daily snapshot
        self.save_daily_snapshot()

        logger.info(f"Simulation {self.sim_id} stopped")

    def run_once(self):
        """Run a single iteration - useful for scheduled execution"""
        logger.info(f"Running single iteration for {self.sim_id}")

        # Get and process current signals
        signals = self.signal_listener.get_current_signals(filter_processed=True)
        for signal in signals:
            self.process_signal(signal.to_dict())
            self.signal_listener.mark_signal_processed(signal)

        # Update prices and check exits
        if self.portfolio.positions:
            prices = self._fetch_current_prices()
            if prices:
                self.update_prices_and_check_exits(prices)

        logger.info(f"Iteration complete. Open positions: {self.portfolio.open_position_count}")

    def end_of_day(self):
        """End of day processing"""
        logger.info(f"Running EOD for {self.sim_id}")

        # Save daily snapshot
        self.save_daily_snapshot()

        # Clear KC cache for next day
        self.kc_calculator.clear_cache()

        # Log summary
        summary = self.get_portfolio_summary()
        logger.info(f"EOD Summary - Value: {summary['current_value']:,.0f}, P&L: {summary['total_pnl']:,.0f} ({summary['total_pnl_pct']:.2f}%)")


def run_simulation(sim_id: str, continuous: bool = True):
    """Run a simulation"""
    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    runner = BaseSimulationRunner(sim_id, config)

    if continuous:
        runner.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            runner.stop()
    else:
        runner.run_once()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run VSR Simulation')
    parser.add_argument('--sim-id', default='sim_1', help='Simulation ID')
    parser.add_argument('--once', action='store_true', help='Run single iteration')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    run_simulation(args.sim_id, continuous=not args.once)
