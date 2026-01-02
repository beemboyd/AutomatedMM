"""
Signal Listener for Simulations
Monitors Long Reversal Daily and Short Reversal Daily scans
Matches exact logic used for Telegram alerts
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from threading import Thread, Event
from dataclasses import dataclass, asdict
import pandas as pd

logger = logging.getLogger(__name__)


def parse_score(score_str) -> float:
    """Parse score from 'X/Y' format to percentage (0-100)"""
    if pd.isna(score_str):
        return 0.0
    if isinstance(score_str, (int, float)):
        return float(score_str)
    try:
        if '/' in str(score_str):
            num, denom = str(score_str).split('/')
            return (float(num) / float(denom)) * 100
        return float(score_str)
    except:
        return 0.0


@dataclass
class VSRSignal:
    """Represents a trading signal"""
    ticker: str
    timestamp: str
    price: float
    vsr_score: float
    vsr_momentum: float
    vsr_ratio: float
    pattern: str
    sector: str
    liquidity_grade: str
    signal_type: str = 'long'  # 'long' or 'short'
    stop_loss: float = 0.0
    target1: float = 0.0
    target2: float = 0.0
    risk_reward: float = 0.0
    metadata: Dict = None

    def to_dict(self) -> Dict:
        return asdict(self)


class VSRSignalListener:
    """
    Listens for signals from:
    - Long signals: Long_Reversal_Daily scans (same as Telegram alerts)
    - Short signals: Short_Reversal_Daily scans (same as Telegram alerts)
    """

    def __init__(self, config: Dict, signal_type: str = 'long', sim_id: str = None):
        """
        Initialize signal listener

        Args:
            config: Configuration dictionary
            signal_type: 'long' or 'short' - determines which data source to read
            sim_id: Simulation ID to get specific entry filter settings
        """
        self.config = config
        self.signal_type = signal_type

        # Get min_score from simulation config entry_filter, or use defaults
        # Long Reversal uses X/7 scoring (5/7 = 71.4%), Short uses X/11 (6/11 = 54.5%)
        # Default: 70% for longs (5/7), 50% for shorts (6/11 passes)
        default_min_score = 70 if signal_type in ('long', 'long_daily') else 50

        if sim_id:
            sim_config = config.get('simulations', {}).get(sim_id, {})
            entry_filter = sim_config.get('entry_filter', {})
            self.min_score = entry_filter.get('min_score', default_min_score)
            self.min_momentum = entry_filter.get('min_momentum', 0)
        else:
            self.min_score = default_min_score
            self.min_momentum = 0  # Momentum_5D can be negative

        # Data paths based on signal type
        self.base_path = Path(__file__).parent.parent.parent

        if signal_type == 'long':
            # Long Reversal Hourly outputs - same source as Telegram alerts
            self.scan_path = self.base_path / 'results-h'
            self.scan_pattern = 'Long_Reversal_Hourly_*.xlsx'
        elif signal_type == 'long_daily':
            # Long Reversal Daily (FNO Liquid) - daily timeframe signals
            self.scan_path = self.base_path / 'FNO' / 'Long' / 'Liquid'
            self.scan_pattern = 'Long_Reversal_Daily_*.xlsx'
        else:  # short
            # Short Reversal Daily (FNO Liquid) - intraday short candidates
            self.scan_path = self.base_path / 'FNO' / 'Short' / 'Liquid'
            self.scan_pattern = 'Short_Reversal_Daily_*.xlsx'

        # State tracking
        self._processed_signals = set()
        self._last_scan_time = None
        self._callbacks = []
        self._stop_event = Event()
        self._listener_thread = None

        logger.info(f"VSR Signal Listener ({signal_type.upper()}) initialized - min_score: {self.min_score}, min_momentum: {self.min_momentum}")

    def register_callback(self, callback: Callable[[VSRSignal], None]):
        """Register a callback to be called when new signals arrive"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, signal: VSRSignal):
        """Notify all registered callbacks of a new signal"""
        for callback in self._callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {e}")

    def _generate_signal_id(self, ticker: str, timestamp: str) -> str:
        """Generate unique signal ID"""
        ts_minute = timestamp[:16] if len(timestamp) >= 16 else timestamp
        return f"{self.signal_type}_{ticker}_{ts_minute}"

    def get_latest_scan(self) -> Optional[pd.DataFrame]:
        """Get the most recent scan results from Long/Short Reversal Hourly"""
        try:
            scan_files = list(self.scan_path.glob(self.scan_pattern))
            if not scan_files:
                logger.warning(f"No {self.signal_type} scan files found in {self.scan_path}")
                return None

            latest_file = max(scan_files, key=lambda p: p.stat().st_mtime)
            file_time = datetime.fromtimestamp(latest_file.stat().st_mtime)

            df = pd.read_excel(latest_file)
            df['scan_file'] = latest_file.name
            df['scan_timestamp'] = file_time.isoformat()

            logger.debug(f"Loaded {len(df)} signals from {latest_file.name}")
            return df

        except Exception as e:
            logger.error(f"Error reading scan: {e}")
            return None

    def get_persistence_data(self) -> Dict:
        """Get current persistence data"""
        try:
            if not self.persistence_path.exists():
                return {}
            with open(self.persistence_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading persistence data: {e}")
            return {}

    def get_current_signals(self, filter_processed: bool = True) -> List[VSRSignal]:
        """Get current signals from Long/Short Reversal Hourly scans"""
        signals = []

        df = self.get_latest_scan()
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                try:
                    ticker = row.get('Ticker', row.get('ticker', ''))
                    if not ticker:
                        continue

                    # Parse score from "X/Y" format (e.g., "5/7" = 71.4%)
                    score = parse_score(row.get('Score', 0))

                    # Get momentum (Momentum_5D for reversal scans)
                    momentum = float(row.get('Momentum_5D', row.get('Momentum', 0)) or 0)

                    # Check minimum score threshold
                    if score < self.min_score:
                        continue

                    timestamp = row.get('scan_timestamp', datetime.now().isoformat())
                    signal_id = self._generate_signal_id(ticker, timestamp)

                    if filter_processed and signal_id in self._processed_signals:
                        continue

                    # Get price and other fields
                    price = float(row.get('Entry_Price', row.get('Close', 0)) or 0)
                    stop_loss = float(row.get('Stop_Loss', 0) or 0)
                    target1 = float(row.get('Target1', 0) or 0)
                    target2 = float(row.get('Target2', 0) or 0)
                    risk_reward = float(row.get('Risk_Reward_Ratio', 0) or 0)
                    volume_ratio = float(row.get('Volume_Ratio', 0) or 0)

                    signal = VSRSignal(
                        ticker=ticker,
                        timestamp=timestamp,
                        price=price,
                        vsr_score=score,
                        vsr_momentum=momentum,
                        vsr_ratio=volume_ratio,
                        pattern=str(row.get('Pattern', f'{self.signal_type.upper()}_Reversal')),
                        sector=str(row.get('Sector', 'Unknown')),
                        liquidity_grade='A',  # Reversal scans are pre-filtered for liquidity
                        signal_type=self.signal_type,
                        stop_loss=stop_loss,
                        target1=target1,
                        target2=target2,
                        risk_reward=risk_reward,
                        metadata={
                            'signal_id': signal_id,
                            'source': f'{self.signal_type}_reversal_hourly',
                            'scan_file': row.get('scan_file', ''),
                            'conditions_met': str(row.get('Conditions_Met', '')),
                            'description': str(row.get('Description', ''))
                        }
                    )
                    signals.append(signal)

                except Exception as e:
                    logger.warning(f"Error processing row for {row.get('Ticker', 'unknown')}: {e}")
                    continue

        return signals

    def mark_signal_processed(self, signal: VSRSignal):
        """Mark a signal as processed"""
        signal_id = signal.metadata.get('signal_id')
        if signal_id:
            self._processed_signals.add(signal_id)

    def start_listening(self, poll_interval: int = 60):
        """Start background thread to poll for new signals"""
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener already running")
            return

        self._stop_event.clear()
        self._listener_thread = Thread(target=self._poll_loop, args=(poll_interval,), daemon=True)
        self._listener_thread.start()
        logger.info(f"{self.signal_type.upper()} signal listener started with {poll_interval}s poll interval")

    def stop_listening(self):
        """Stop the background listener"""
        self._stop_event.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        logger.info(f"{self.signal_type.upper()} signal listener stopped")

    def _poll_loop(self, interval: int):
        """Background polling loop"""
        while not self._stop_event.is_set():
            try:
                signals = self.get_current_signals(filter_processed=True)
                for signal in signals:
                    self._notify_callbacks(signal)
                    self.mark_signal_processed(signal)

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(interval)

    def get_signal_stats(self) -> Dict:
        """Get signal statistics"""
        return {
            'signal_type': self.signal_type,
            'signals_processed': len(self._processed_signals),
            'min_score_filter': self.min_score,
            'min_momentum_filter': self.min_momentum,
            'scan_path': str(self.scan_path)
        }


class TDMA2FilterSignalListener:
    """
    Listens for signals from TD MA II Filter Dashboard (port 3005)
    Fetches entry_valid tickers that have both MA2 Fast and Slow blue with Fast > Slow
    """

    def __init__(self, config: Dict, sim_id: str = None):
        """
        Initialize TD MA II Filter signal listener

        Args:
            config: Configuration dictionary
            sim_id: Simulation ID to get specific entry filter settings
        """
        self.config = config
        self.signal_type = 'td_ma2_filter'

        # API endpoint
        signal_source_config = config.get('signal_sources', {}).get('td_ma2_filter', {})
        self.api_url = signal_source_config.get('api_url', 'http://localhost:3005/api/filtered-tickers')
        self.category = signal_source_config.get('category', 'entry_valid')

        # Get entry filter settings from simulation config
        if sim_id:
            sim_config = config.get('simulations', {}).get(sim_id, {})
            entry_filter = sim_config.get('entry_filter', {})
            self.skip_exhausted = entry_filter.get('skip_exhausted', True)
        else:
            self.skip_exhausted = True

        # State tracking
        self._processed_signals = set()
        self._callbacks = []
        self._stop_event = Event()
        self._listener_thread = None

        logger.info(f"TD MA II Filter Signal Listener initialized - API: {self.api_url}, skip_exhausted: {self.skip_exhausted}")

    def register_callback(self, callback: Callable[[VSRSignal], None]):
        """Register a callback to be called when new signals arrive"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, signal: VSRSignal):
        """Notify all registered callbacks of a new signal"""
        for callback in self._callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {e}")

    def _generate_signal_id(self, ticker: str, timestamp: str) -> str:
        """Generate unique signal ID"""
        # Use date only for daily signals to avoid re-entry same day
        ts_date = timestamp[:10] if len(timestamp) >= 10 else timestamp
        return f"td_ma2_{ticker}_{ts_date}"

    def get_current_signals(self, filter_processed: bool = True) -> List[VSRSignal]:
        """Get current signals from TD MA II Filter Dashboard API"""
        import requests

        signals = []

        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Get entry_valid tickers (both blue + fast > slow)
            entry_valid = data.get('categories', {}).get(self.category, [])
            timestamp = data.get('timestamp', datetime.now().isoformat())

            for ticker_data in entry_valid:
                try:
                    ticker = ticker_data.get('ticker', '')
                    if not ticker:
                        continue

                    # Skip exhausted tickers if configured
                    exhaustion_level = ticker_data.get('exhaustion_level', 'NONE')
                    if self.skip_exhausted and exhaustion_level in ('EXHAUSTED', 'CONFIRMED'):
                        logger.debug(f"Skipping {ticker} - exhaustion level: {exhaustion_level}")
                        continue

                    signal_id = self._generate_signal_id(ticker, timestamp)

                    if filter_processed and signal_id in self._processed_signals:
                        continue

                    # Get price and MA data
                    price = float(ticker_data.get('close', 0))
                    score = float(ticker_data.get('score', 0))
                    momentum = float(ticker_data.get('momentum', 0))
                    vsr = float(ticker_data.get('vsr', 0))

                    signal = VSRSignal(
                        ticker=ticker,
                        timestamp=timestamp,
                        price=price,
                        vsr_score=score,
                        vsr_momentum=momentum,
                        vsr_ratio=vsr,
                        pattern='TD_MA2_Entry_Valid',
                        sector='Unknown',
                        liquidity_grade='A',
                        signal_type='long',
                        metadata={
                            'signal_id': signal_id,
                            'source': 'td_ma2_filter_dashboard',
                            'ma2_fast': ticker_data.get('ma2_fast'),
                            'ma2_slow': ticker_data.get('ma2_slow'),
                            'fast_blue': ticker_data.get('fast_blue'),
                            'slow_blue': ticker_data.get('slow_blue'),
                            'entry_valid': ticker_data.get('entry_valid'),
                            'exhaustion_level': exhaustion_level,
                            'setup_count': ticker_data.get('setup_count', 0),
                            'countdown': ticker_data.get('countdown', 0)
                        }
                    )
                    signals.append(signal)

                except Exception as e:
                    logger.warning(f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                    continue

            logger.info(f"Fetched {len(signals)} entry_valid signals from TD MA II Filter")

        except Exception as e:
            logger.error(f"Error fetching from TD MA II Filter API: {e}")

        return signals

    def mark_signal_processed(self, signal: VSRSignal):
        """Mark a signal as processed"""
        signal_id = signal.metadata.get('signal_id')
        if signal_id:
            self._processed_signals.add(signal_id)

    def start_listening(self, poll_interval: int = 60):
        """Start background thread to poll for new signals"""
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener already running")
            return

        self._stop_event.clear()
        self._listener_thread = Thread(target=self._poll_loop, args=(poll_interval,), daemon=True)
        self._listener_thread.start()
        logger.info(f"TD MA II Filter signal listener started with {poll_interval}s poll interval")

    def stop_listening(self):
        """Stop the background listener"""
        self._stop_event.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        logger.info("TD MA II Filter signal listener stopped")

    def _poll_loop(self, interval: int):
        """Background polling loop"""
        while not self._stop_event.is_set():
            try:
                signals = self.get_current_signals(filter_processed=True)
                for signal in signals:
                    self._notify_callbacks(signal)
                    self.mark_signal_processed(signal)

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(interval)

    def get_signal_stats(self) -> Dict:
        """Get signal statistics"""
        return {
            'signal_type': self.signal_type,
            'signals_processed': len(self._processed_signals),
            'api_url': self.api_url,
            'skip_exhausted': self.skip_exhausted
        }


class TickflowSignalListener:
    """
    Listens for signals from TickFlow Dashboard (port 6063)
    Fetches 1K tick section tickers where RED>0 & WM>0 & WM>9EMA(WM)
    """

    def __init__(self, config: Dict, sim_id: str = None):
        """
        Initialize TickFlow signal listener

        Args:
            config: Configuration dictionary
            sim_id: Simulation ID to get specific entry filter settings
        """
        self.config = config
        self.signal_type = 'tickflow_1k'

        # API endpoint
        signal_source_config = config.get('signal_sources', {}).get('tickflow_1k', {})
        self.api_url = signal_source_config.get('api_url', 'http://localhost:6063/api/1k-tickers')

        # State tracking
        self._processed_signals = set()
        self._callbacks = []
        self._stop_event = Event()
        self._listener_thread = None

        logger.info(f"TickFlow 1K Signal Listener initialized - API: {self.api_url}")

    def register_callback(self, callback: Callable[[VSRSignal], None]):
        """Register a callback to be called when new signals arrive"""
        self._callbacks.append(callback)

    def _notify_callbacks(self, signal: VSRSignal):
        """Notify all registered callbacks of a new signal"""
        for callback in self._callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Error in signal callback: {e}")

    def _generate_signal_id(self, ticker: str, timestamp: str) -> str:
        """Generate unique signal ID"""
        # Use date + hour to avoid duplicate entries within same hour
        ts_hour = timestamp[:13] if len(timestamp) >= 13 else timestamp
        return f"tickflow_1k_{ticker}_{ts_hour}"

    def get_current_signals(self, filter_processed: bool = True) -> List[VSRSignal]:
        """Get current signals from TickFlow 1K Dashboard API"""
        import requests

        signals = []

        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            tickers = data.get('tickers', [])
            timestamp = data.get('timestamp', datetime.now().isoformat())

            for ticker_data in tickers:
                try:
                    ticker = ticker_data.get('ticker', '')
                    if not ticker:
                        continue

                    signal_id = self._generate_signal_id(ticker, timestamp)

                    if filter_processed and signal_id in self._processed_signals:
                        continue

                    # Get price and metrics from TickFlow data
                    price = float(ticker_data.get('price', 0))
                    wm = float(ticker_data.get('wm', 0))
                    wm_sig = float(ticker_data.get('wm_sig', 0))
                    cvd_ma_50 = float(ticker_data.get('cvd_ma_50', 0))
                    cvd_ma_21 = float(ticker_data.get('cvd_ma_21', 0))
                    bar_count = int(ticker_data.get('bar_count', 0))

                    signal = VSRSignal(
                        ticker=ticker,
                        timestamp=timestamp,
                        price=price,
                        vsr_score=0,  # Not applicable for TickFlow
                        vsr_momentum=wm_sig,  # Use WM_Sig as momentum indicator
                        vsr_ratio=wm,
                        pattern='TickFlow_1K_Bullish',
                        sector='Unknown',
                        liquidity_grade='A',
                        signal_type='long',
                        metadata={
                            'signal_id': signal_id,
                            'source': 'tickflow_1k_dashboard',
                            'wm': wm,
                            'wm_sig': wm_sig,
                            'cvd_ma_21': cvd_ma_21,
                            'cvd_ma_50': cvd_ma_50,
                            'bar_count': bar_count,
                            'tick_level': 1000
                        }
                    )
                    signals.append(signal)

                except Exception as e:
                    logger.warning(f"Error processing ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                    continue

            logger.info(f"Fetched {len(signals)} signals from TickFlow 1K")

        except Exception as e:
            logger.error(f"Error fetching from TickFlow API: {e}")

        return signals

    def mark_signal_processed(self, signal: VSRSignal):
        """Mark a signal as processed"""
        signal_id = signal.metadata.get('signal_id')
        if signal_id:
            self._processed_signals.add(signal_id)

    def start_listening(self, poll_interval: int = 60):
        """Start background thread to poll for new signals"""
        if self._listener_thread and self._listener_thread.is_alive():
            logger.warning("Listener already running")
            return

        self._stop_event.clear()
        self._listener_thread = Thread(target=self._poll_loop, args=(poll_interval,), daemon=True)
        self._listener_thread.start()
        logger.info(f"TickFlow 1K signal listener started with {poll_interval}s poll interval")

    def stop_listening(self):
        """Stop the background listener"""
        self._stop_event.set()
        if self._listener_thread:
            self._listener_thread.join(timeout=5)
        logger.info("TickFlow 1K signal listener stopped")

    def _poll_loop(self, interval: int):
        """Background polling loop"""
        while not self._stop_event.is_set():
            try:
                signals = self.get_current_signals(filter_processed=True)
                for signal in signals:
                    self._notify_callbacks(signal)
                    self.mark_signal_processed(signal)

            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            self._stop_event.wait(interval)

    def get_signal_stats(self) -> Dict:
        """Get signal statistics"""
        return {
            'signal_type': self.signal_type,
            'signals_processed': len(self._processed_signals),
            'api_url': self.api_url
        }


class ManualSignalInjector:
    """Allows manual injection of signals for testing"""

    def __init__(self, listener: VSRSignalListener):
        self.listener = listener

    def inject_signal(self, ticker: str, price: float, score: float = 70,
                      momentum: float = 5.0, pattern: str = 'Manual_Entry',
                      signal_type: str = 'long') -> VSRSignal:
        """Inject a manual signal"""
        signal = VSRSignal(
            ticker=ticker,
            timestamp=datetime.now().isoformat(),
            price=price,
            vsr_score=score,
            vsr_momentum=momentum,
            vsr_ratio=2.0,
            pattern=pattern,
            sector='Manual',
            liquidity_grade='A',
            signal_type=signal_type,
            metadata={
                'signal_id': f"{signal_type}_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M')}",
                'source': 'manual_injection'
            }
        )

        for callback in self.listener._callbacks:
            try:
                callback(signal)
            except Exception as e:
                logger.error(f"Error in callback for manual signal: {e}")

        return signal


# Factory function for signal listeners
_signal_listeners = {}


def get_signal_listener(config: Dict = None, signal_type: str = 'long', sim_id: str = None):
    """Get or create signal listener for the specified type"""
    global _signal_listeners

    # Use sim_id as key if provided, otherwise just signal_type
    key = sim_id if sim_id else signal_type

    if key not in _signal_listeners:
        if config is None:
            config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
            with open(config_path, 'r') as f:
                config = json.load(f)

        # Use appropriate listener based on signal type
        if signal_type == 'td_ma2_filter':
            _signal_listeners[key] = TDMA2FilterSignalListener(config, sim_id)
        elif signal_type == 'tickflow_1k':
            _signal_listeners[key] = TickflowSignalListener(config, sim_id)
        else:
            _signal_listeners[key] = VSRSignalListener(config, signal_type, sim_id)

    return _signal_listeners[key]
