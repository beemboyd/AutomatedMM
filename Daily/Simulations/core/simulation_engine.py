"""
Base Simulation Engine for VSR Trading Simulations
Handles portfolio management, position sizing, trade execution, and P&L tracking
Supports both Long and Short positions with different charge structures
"""

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, date, time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

from .database_manager import SimulationDatabase

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents an open position"""
    trade_id: int
    ticker: str
    direction: str  # 'long' or 'short'
    entry_price: float
    quantity: int
    stop_loss: float
    target: Optional[float]
    kc_lower: float
    kc_upper: float
    kc_middle: float
    entry_timestamp: str
    sl_type: str = 'fixed'  # 'fixed' or 'psar'
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0

    def update_current_price(self, price: float):
        """Update current price and recalculate unrealized P&L"""
        self.current_price = price
        if self.direction == 'long':
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:  # short
            self.unrealized_pnl = (self.entry_price - price) * self.quantity
        self.unrealized_pnl_pct = (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100


@dataclass
class Portfolio:
    """Portfolio state"""
    initial_capital: float = 10000000  # 1 Crore
    cash: float = 10000000
    invested: float = 0.0
    positions: Dict[str, Position] = field(default_factory=dict)
    total_charges_paid: float = 0.0
    realized_pnl: float = 0.0

    @property
    def total_value(self) -> float:
        """Total portfolio value including unrealized P&L"""
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.cash + self.invested + unrealized

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L"""
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def total_pnl(self) -> float:
        """Total P&L (realized + unrealized)"""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_pnl_pct(self) -> float:
        """Total P&L percentage"""
        return (self.total_pnl / self.initial_capital) * 100

    @property
    def open_position_count(self) -> int:
        """Number of open positions"""
        return len(self.positions)


class BaseSimulationEngine(ABC):
    """
    Base class for VSR Trading Simulations
    Extend this class to implement specific simulation logic
    """

    def __init__(self, sim_id: str, config: Dict):
        self.sim_id = sim_id
        self.config = config
        self.global_config = config.get('global', {})
        self.sim_config = config.get('simulations', {}).get(sim_id, {})
        self.charges_config = config.get('charges', {})

        # Initialize database
        self.db = SimulationDatabase(sim_id)

        # Initialize portfolio
        self.portfolio = Portfolio(
            initial_capital=self.global_config.get('initial_capital', 10000000),
            cash=self.global_config.get('initial_capital', 10000000)
        )

        # Configuration
        self.position_size_pct = self.global_config.get('position_size_pct', 5.0)
        self.max_positions = self.global_config.get('max_positions', 20)

        # Direction and charges
        self.direction = self.sim_config.get('direction', 'long')
        self.sl_type = self.sim_config.get('sl_type', 'kc_lower')
        self.can_hold_overnight = self.sim_config.get('can_hold_overnight', True)
        self.eod_close_required = self.sim_config.get('eod_close_required', False)

        # Charges based on direction
        if self.direction == 'long':
            self.charges_per_leg_pct = self.charges_config.get('long_per_leg_pct', 0.15)
        else:
            self.charges_per_leg_pct = self.charges_config.get('short_per_leg_pct', 0.035)

        # Override from sim config if specified
        if 'charges_per_leg_pct' in self.sim_config:
            self.charges_per_leg_pct = self.sim_config['charges_per_leg_pct']

        # Keltner Channel config
        self.kc_config = config.get('keltner_channel', {})

        # PSAR config
        self.psar_config = config.get('psar', {})

        # State tracking
        self.daily_trades_opened = 0
        self.daily_trades_closed = 0
        self.daily_winning = 0
        self.daily_losing = 0
        self.current_date = None
        self.max_drawdown = 0.0
        self.peak_value = self.portfolio.initial_capital

        # Load existing state
        self._load_state()

        logger.info(f"Simulation {sim_id} ({self.direction.upper()}) initialized - Capital: {self.portfolio.initial_capital:,.0f}, Charges: {self.charges_per_leg_pct}%/leg")

    def _load_state(self):
        """Load existing portfolio state from database"""
        state = self.db.get_current_portfolio_state()
        if state:
            self.portfolio.cash = state['cash']
            self.portfolio.invested = state['invested']
            self.portfolio.realized_pnl = state.get('total_pnl', 0) - self.portfolio.unrealized_pnl

        # Load open positions
        open_trades = self.db.get_open_trades()
        for trade in open_trades:
            pos = Position(
                trade_id=trade['id'],
                ticker=trade['ticker'],
                direction=self.direction,
                entry_price=trade['entry_price'],
                quantity=trade['quantity'],
                stop_loss=trade['stop_loss'],
                target=trade.get('target'),
                kc_lower=trade.get('kc_lower', 0),
                kc_upper=trade.get('kc_upper', 0),
                kc_middle=trade.get('kc_middle', 0),
                entry_timestamp=trade['entry_timestamp'],
                sl_type=self.sl_type,
                current_price=trade['entry_price']
            )
            self.portfolio.positions[trade['ticker']] = pos

    def calculate_position_size(self, price: float) -> Tuple[int, float]:
        """Calculate position size based on portfolio value and position size percentage"""
        portfolio_value = self.portfolio.total_value
        position_value = portfolio_value * (self.position_size_pct / 100)
        quantity = int(position_value / price)
        actual_value = quantity * price
        return quantity, actual_value

    def calculate_charges(self, value: float) -> float:
        """Calculate charges for a trade leg"""
        return value * (self.charges_per_leg_pct / 100)

    def can_open_position(self, ticker: str) -> Tuple[bool, str]:
        """Check if a new position can be opened"""
        if ticker in self.portfolio.positions:
            return False, f"Already have open position in {ticker}"

        if self.portfolio.open_position_count >= self.max_positions:
            return False, f"Max positions ({self.max_positions}) reached"

        min_position = self.portfolio.total_value * (self.position_size_pct / 100)
        if self.portfolio.cash < min_position:
            return False, f"Insufficient cash ({self.portfolio.cash:,.0f} < {min_position:,.0f})"

        # Check trading hours for short positions (no entry after 3 PM)
        if self.direction == 'short':
            now = datetime.now().time()
            if now >= time(15, 0):
                return False, "Short positions cannot be opened after 3:00 PM"

        return True, "OK"

    def open_position(self, ticker: str, signal_price: float, entry_price: float,
                      kc_data: Dict, vsr_score: float = None, vsr_momentum: float = None,
                      signal_pattern: str = None, metadata: Dict = None) -> Optional[int]:
        """Open a new position"""
        can_open, reason = self.can_open_position(ticker)
        if not can_open:
            logger.warning(f"Cannot open position in {ticker}: {reason}")
            self.db.log_signal(
                ticker=ticker,
                timestamp=datetime.now().isoformat(),
                price=signal_price,
                vsr_score=vsr_score,
                vsr_momentum=vsr_momentum,
                pattern=signal_pattern,
                action_taken='REJECTED',
                rejection_reason=reason
            )
            return None

        quantity, position_value = self.calculate_position_size(entry_price)
        if quantity == 0:
            logger.warning(f"Position size too small for {ticker} at {entry_price}")
            return None

        entry_charges = self.calculate_charges(position_value)
        stop_loss = self._get_stop_loss(kc_data, entry_price)

        trade_id = self.db.create_trade(
            ticker=ticker,
            signal_price=signal_price,
            signal_timestamp=datetime.now().isoformat(),
            vsr_score=vsr_score,
            vsr_momentum=vsr_momentum,
            signal_pattern=signal_pattern,
            metadata={'direction': self.direction, 'sl_type': self.sl_type, **(metadata or {})}
        )

        self.db.execute_trade(
            trade_id=trade_id,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            target=kc_data.get('upper') if self.direction == 'long' else kc_data.get('lower'),
            kc_lower=kc_data.get('lower'),
            kc_upper=kc_data.get('upper'),
            kc_middle=kc_data.get('middle')
        )

        self.portfolio.cash -= (position_value + entry_charges)
        self.portfolio.invested += position_value
        self.portfolio.total_charges_paid += entry_charges

        position = Position(
            trade_id=trade_id,
            ticker=ticker,
            direction=self.direction,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            target=kc_data.get('upper') if self.direction == 'long' else kc_data.get('lower'),
            kc_lower=kc_data.get('lower', 0),
            kc_upper=kc_data.get('upper', 0),
            kc_middle=kc_data.get('middle', 0),
            entry_timestamp=datetime.now().isoformat(),
            sl_type=self.sl_type,
            current_price=entry_price
        )
        self.portfolio.positions[ticker] = position

        self.db.log_signal(
            ticker=ticker,
            timestamp=datetime.now().isoformat(),
            price=signal_price,
            vsr_score=vsr_score,
            vsr_momentum=vsr_momentum,
            pattern=signal_pattern,
            action_taken='EXECUTED',
            metadata={'trade_id': trade_id, 'quantity': quantity, 'stop_loss': stop_loss, 'direction': self.direction}
        )

        self.daily_trades_opened += 1
        self._save_portfolio_state()

        logger.info(f"Opened {self.direction.upper()} position: {ticker} @ {entry_price:.2f} x {quantity} = {position_value:,.0f} | SL: {stop_loss:.2f}")

        return trade_id

    def close_position(self, ticker: str, exit_price: float, exit_reason: str) -> Optional[float]:
        """Close an open position"""
        if ticker not in self.portfolio.positions:
            logger.warning(f"No open position in {ticker}")
            return None

        position = self.portfolio.positions[ticker]

        # Calculate P&L based on direction
        if position.direction == 'long':
            gross_pnl = (exit_price - position.entry_price) * position.quantity
        else:  # short
            gross_pnl = (position.entry_price - exit_price) * position.quantity

        exit_value = exit_price * position.quantity
        exit_charges = self.calculate_charges(exit_value)
        net_pnl = gross_pnl - exit_charges

        self.db.close_trade(position.trade_id, exit_price, exit_reason)

        self.portfolio.cash += (exit_value - exit_charges)
        self.portfolio.invested -= (position.entry_price * position.quantity)
        self.portfolio.realized_pnl += net_pnl
        self.portfolio.total_charges_paid += exit_charges

        del self.portfolio.positions[ticker]

        self.daily_trades_closed += 1
        if net_pnl > 0:
            self.daily_winning += 1
        elif net_pnl < 0:
            self.daily_losing += 1

        self._update_drawdown()
        self._save_portfolio_state()

        logger.info(f"Closed {position.direction.upper()} position: {ticker} @ {exit_price:.2f} | P&L: {net_pnl:,.0f} ({exit_reason})")

        return net_pnl

    def update_position_prices(self, price_updates: Dict[str, float]):
        """Update current prices for all positions"""
        for ticker, price in price_updates.items():
            if ticker in self.portfolio.positions:
                self.portfolio.positions[ticker].update_current_price(price)

        self._update_drawdown()
        self._save_portfolio_state()

    def check_stop_losses(self, current_prices: Dict[str, float]) -> List[str]:
        """Check stop losses for all positions"""
        stopped_out = []
        for ticker, position in list(self.portfolio.positions.items()):
            current_price = current_prices.get(ticker)
            if not current_price:
                continue

            if position.direction == 'long':
                # Long: stop triggered if price <= stop_loss
                if current_price <= position.stop_loss:
                    self.close_position(ticker, current_price, 'STOP_LOSS')
                    stopped_out.append(ticker)
            else:
                # Short: stop triggered if price >= stop_loss
                if current_price >= position.stop_loss:
                    self.close_position(ticker, current_price, 'STOP_LOSS')
                    stopped_out.append(ticker)

        return stopped_out

    def check_targets(self, current_prices: Dict[str, float]) -> List[str]:
        """Check targets for all positions"""
        targets_hit = []
        for ticker, position in list(self.portfolio.positions.items()):
            if not position.target:
                continue
            current_price = current_prices.get(ticker)
            if not current_price:
                continue

            if position.direction == 'long':
                # Long: target hit if price >= target
                if current_price >= position.target:
                    self.close_position(ticker, current_price, 'TARGET_HIT')
                    targets_hit.append(ticker)
            else:
                # Short: target hit if price <= target
                if current_price <= position.target:
                    self.close_position(ticker, current_price, 'TARGET_HIT')
                    targets_hit.append(ticker)

        return targets_hit

    def close_all_positions(self, current_prices: Dict[str, float], reason: str = 'EOD_CLOSE') -> int:
        """Close all open positions (used for EOD)"""
        closed_count = 0
        for ticker in list(self.portfolio.positions.keys()):
            price = current_prices.get(ticker)
            if price:
                self.close_position(ticker, price, reason)
                closed_count += 1
            else:
                # Use last known price if current not available
                position = self.portfolio.positions[ticker]
                self.close_position(ticker, position.current_price or position.entry_price, reason)
                closed_count += 1
        return closed_count

    def check_eod_close(self, current_prices: Dict[str, float]) -> bool:
        """Check if EOD close is required and execute"""
        if not self.eod_close_required:
            return False

        now = datetime.now().time()
        # Get EOD close time from config (default 15:00 = 3 PM)
        eod_time_str = self.global_config.get('eod_close_time', '15:00')
        hour, minute = map(int, eod_time_str.split(':'))
        eod_time = time(hour, minute)

        if now >= eod_time and self.portfolio.open_position_count > 0:
            logger.info(f"EOD close triggered for {self.sim_id} - closing {self.portfolio.open_position_count} positions")
            self.close_all_positions(current_prices, 'EOD_CLOSE')
            return True

        return False

    def update_trailing_stop(self, ticker: str, new_stop: float):
        """Update stop loss for a position (used for PSAR trailing)"""
        if ticker not in self.portfolio.positions:
            return

        position = self.portfolio.positions[ticker]

        if position.direction == 'long':
            # For long: only move stop UP
            if new_stop > position.stop_loss:
                position.stop_loss = new_stop
                logger.debug(f"Trailing stop updated for {ticker}: {new_stop:.2f}")
        else:
            # For short: only move stop DOWN
            if new_stop < position.stop_loss:
                position.stop_loss = new_stop
                logger.debug(f"Trailing stop updated for {ticker}: {new_stop:.2f}")

    def _get_stop_loss(self, kc_data: Dict, entry_price: float) -> float:
        """Get stop loss price based on configuration"""
        sl_type = self.sl_type

        if sl_type == 'kc_lower':
            return kc_data.get('lower', entry_price * 0.95)
        elif sl_type == 'kc_upper':
            return kc_data.get('upper', entry_price * 1.05)
        elif sl_type == 'kc_middle':
            return kc_data.get('middle', entry_price)
        elif sl_type == 'psar':
            # For PSAR, initial SL is KC based, then updated dynamically
            if self.direction == 'long':
                return kc_data.get('lower', entry_price * 0.95)
            else:
                return kc_data.get('upper', entry_price * 1.05)
        else:
            if self.direction == 'long':
                return entry_price * 0.95
            else:
                return entry_price * 1.05

    def _update_drawdown(self):
        """Update max drawdown tracking"""
        current_value = self.portfolio.total_value
        if current_value > self.peak_value:
            self.peak_value = current_value
        drawdown = (self.peak_value - current_value) / self.peak_value * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

    def _save_portfolio_state(self):
        """Save current portfolio state to database"""
        self.db.update_portfolio_state(
            cash=self.portfolio.cash,
            invested=self.portfolio.invested,
            total_value=self.portfolio.total_value,
            open_positions=self.portfolio.open_position_count,
            daily_pnl=self.portfolio.realized_pnl,
            total_pnl=self.portfolio.total_pnl,
            metadata={
                'charges_paid': self.portfolio.total_charges_paid,
                'max_drawdown': self.max_drawdown,
                'direction': self.direction
            }
        )

    def save_daily_snapshot(self):
        """Save end of day snapshot"""
        today = date.today().isoformat()
        self.db.save_daily_snapshot(
            date=today,
            opening_capital=self.portfolio.initial_capital,
            closing_capital=self.portfolio.total_value,
            cash=self.portfolio.cash,
            invested=self.portfolio.invested,
            trades_opened=self.daily_trades_opened,
            trades_closed=self.daily_trades_closed,
            winning_trades=self.daily_winning,
            losing_trades=self.daily_losing,
            daily_pnl=self.portfolio.realized_pnl,
            cumulative_pnl=self.portfolio.total_pnl,
            max_drawdown=self.max_drawdown,
            open_positions=self.portfolio.open_position_count,
            metadata={
                'charges_paid': self.portfolio.total_charges_paid,
                'positions': list(self.portfolio.positions.keys()),
                'direction': self.direction
            }
        )
        self.daily_trades_opened = 0
        self.daily_trades_closed = 0
        self.daily_winning = 0
        self.daily_losing = 0

    def get_portfolio_summary(self) -> Dict:
        """Get current portfolio summary for dashboard"""
        stats = self.db.get_statistics()
        return {
            'sim_id': self.sim_id,
            'sim_name': self.sim_config.get('name', f'Simulation {self.sim_id}'),
            'direction': self.direction,
            'sl_type': self.sl_type,
            'initial_capital': self.portfolio.initial_capital,
            'current_value': self.portfolio.total_value,
            'cash': self.portfolio.cash,
            'invested': self.portfolio.invested,
            'realized_pnl': self.portfolio.realized_pnl,
            'unrealized_pnl': self.portfolio.unrealized_pnl,
            'total_pnl': self.portfolio.total_pnl,
            'total_pnl_pct': self.portfolio.total_pnl_pct,
            'open_positions': self.portfolio.open_position_count,
            'max_drawdown': self.max_drawdown,
            'total_charges': self.portfolio.total_charges_paid,
            'charges_per_leg': self.charges_per_leg_pct,
            'statistics': stats,
            'positions': [asdict(p) for p in self.portfolio.positions.values()],
            'last_updated': datetime.now().isoformat()
        }

    def get_positions_detail(self) -> List[Dict]:
        """Get detailed position info for dashboard"""
        return [asdict(p) for p in self.portfolio.positions.values()]

    def reset(self):
        """Reset simulation to initial state"""
        self.db.reset_simulation()
        self.portfolio = Portfolio(
            initial_capital=self.global_config.get('initial_capital', 10000000),
            cash=self.global_config.get('initial_capital', 10000000)
        )
        self.daily_trades_opened = 0
        self.daily_trades_closed = 0
        self.daily_winning = 0
        self.daily_losing = 0
        self.max_drawdown = 0.0
        self.peak_value = self.portfolio.initial_capital
        logger.info(f"Simulation {self.sim_id} reset to initial state")

    @abstractmethod
    def process_signal(self, signal: Dict) -> bool:
        """Process an incoming VSR signal - must be implemented by subclasses"""
        pass

    @abstractmethod
    def should_enter(self, signal: Dict) -> Tuple[bool, str]:
        """Determine if should enter based on signal - must be implemented by subclasses"""
        pass
