#!/usr/bin/env python3
"""
Telegram Alert Backtester

Backtest simulation using Telegram alerts as entry signals.
Compares two exit strategies:
- Sim 1: Exit when price drops below Keltner Channel Lower
- Sim 2: Exit when price drops below Keltner Channel Middle (SMA20)

Data Source: Daily/data/audit_vsr.db (telegram_alerts table)
"""

import os
import sys
import sqlite3
import logging
import configparser
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time

import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from kiteconnect import KiteConnect

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position"""
    ticker: str
    entry_date: str
    entry_price: float
    quantity: int
    position_value: float
    kc_lower: float
    kc_middle: float
    kc_upper: float
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    days_held: int = 0


@dataclass
class SimulationResult:
    """Results from a simulation run"""
    sim_name: str
    exit_strategy: str
    initial_capital: float
    final_capital: float
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    max_win: float
    max_loss: float
    avg_days_held: float
    total_charges: float
    positions: List[Position] = field(default_factory=list)


class TelegramAlertBacktester:
    """
    Backtester for Telegram alert strategies
    """

    def __init__(self, initial_capital: float = 10000000, position_size_pct: float = 5.0,
                 charges_per_leg_pct: float = 0.15, lookback_days: int = 10):
        """
        Initialize backtester

        Args:
            initial_capital: Starting capital (default 1 Crore)
            position_size_pct: Position size as % of portfolio (default 5%)
            charges_per_leg_pct: Trading charges per leg (default 0.15%)
            lookback_days: Days to look back for alerts
        """
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.charges_per_leg_pct = charges_per_leg_pct
        self.lookback_days = lookback_days

        self.base_dir = Path("/Users/maverick/PycharmProjects/India-TS/Daily")
        self.db_path = self.base_dir / "data" / "audit_vsr.db"
        self.output_dir = self.base_dir / "analysis" / "Efficiency"

        self.ist = pytz.timezone('Asia/Kolkata')
        self.kite = None
        self.instrument_map = {}

        # Rate limiting
        self.last_api_call = 0
        self.rate_limit = 3

        self._init_kite()

    def _init_kite(self):
        """Initialize Zerodha connection"""
        try:
            config = configparser.ConfigParser()
            config.read(self.base_dir / 'config.ini')

            if 'API_CREDENTIALS_Sai' in config:
                api_key = config['API_CREDENTIALS_Sai']['api_key']
                access_token = config['API_CREDENTIALS_Sai']['access_token']
            else:
                api_key = config['DEFAULT']['api_key']
                access_token = config['DEFAULT']['access_token']

            self.kite = KiteConnect(api_key=api_key)
            self.kite.set_access_token(access_token)

            instruments = self.kite.instruments("NSE")
            self.instrument_map = {i['tradingsymbol']: i['instrument_token'] for i in instruments}

            logger.info(f"Kite connected, loaded {len(self.instrument_map)} instruments")
        except Exception as e:
            logger.error(f"Failed to init Kite: {e}")

    def _throttle(self):
        """Rate limit API calls"""
        elapsed = time.time() - self.last_api_call
        if elapsed < 1.0 / self.rate_limit:
            time.sleep(1.0 / self.rate_limit - elapsed)
        self.last_api_call = time.time()

    def get_telegram_alerts(self) -> List[Dict]:
        """Get Telegram alerts from the database"""
        if not self.db_path.exists():
            logger.error(f"Database not found: {self.db_path}")
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        start_date = (datetime.now() - timedelta(days=self.lookback_days)).strftime('%Y-%m-%d')

        query = """
            SELECT
                ticker,
                MIN(timestamp) as first_alert_time,
                current_price as entry_price,
                score,
                momentum,
                liquidity_grade
            FROM telegram_alerts
            WHERE DATE(timestamp) >= ?
            GROUP BY ticker
            ORDER BY first_alert_time
        """

        cursor = conn.execute(query, (start_date,))
        rows = cursor.fetchall()

        alerts = []
        for row in rows:
            entry_price = row['entry_price']
            if entry_price and isinstance(entry_price, (int, float)) and entry_price > 0:
                alerts.append({
                    'ticker': row['ticker'],
                    'alert_time': row['first_alert_time'],
                    'entry_price': float(entry_price),
                    'score': row['score'],
                    'momentum': row['momentum'],
                    'liquidity': row['liquidity_grade']
                })

        conn.close()
        logger.info(f"Found {len(alerts)} alerts in past {self.lookback_days} days")
        return alerts

    def get_historical_data(self, ticker: str, from_date: str, to_date: str) -> Optional[pd.DataFrame]:
        """Get historical daily OHLC data"""
        if not self.kite or ticker not in self.instrument_map:
            return None

        try:
            self._throttle()
            token = self.instrument_map[ticker]

            data = self.kite.historical_data(
                instrument_token=token,
                from_date=from_date,
                to_date=to_date,
                interval='day'
            )

            if not data:
                return None

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date']).dt.date
            return df

        except Exception as e:
            logger.warning(f"Error getting historical data for {ticker}: {e}")
            return None

    def calculate_keltner_channel(self, df: pd.DataFrame, ema_period: int = 20,
                                   atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
        """Calculate Keltner Channel bands"""
        # EMA of close (middle band)
        df['kc_middle'] = df['close'].ewm(span=ema_period, adjust=False).mean()

        # True Range and ATR
        df['tr'] = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        ], axis=1).max(axis=1)

        df['atr'] = df['tr'].rolling(window=atr_period).mean()

        # Upper and Lower bands
        df['kc_upper'] = df['kc_middle'] + (multiplier * df['atr'])
        df['kc_lower'] = df['kc_middle'] - (multiplier * df['atr'])

        return df

    def simulate_position(self, alert: Dict, exit_type: str) -> Optional[Position]:
        """
        Simulate a single position

        Args:
            alert: Alert data with ticker, entry_price, alert_time
            exit_type: 'kc_lower' or 'kc_middle'

        Returns:
            Position object with results
        """
        ticker = alert['ticker']
        entry_price = alert['entry_price']
        alert_time = alert['alert_time']

        # Parse alert date
        try:
            alert_date = datetime.fromisoformat(alert_time.replace('Z', '+00:00')).date()
        except:
            alert_date = datetime.strptime(alert_time[:10], '%Y-%m-%d').date()

        # Get historical data from alert date to today
        from_date = (alert_date - timedelta(days=30)).strftime('%Y-%m-%d')  # Extra days for KC calc
        to_date = datetime.now().strftime('%Y-%m-%d')

        df = self.get_historical_data(ticker, from_date, to_date)
        if df is None or len(df) < 25:
            logger.warning(f"Insufficient data for {ticker}")
            return None

        # Calculate KC
        df = self.calculate_keltner_channel(df)

        # Find entry day in data
        entry_idx = None
        for i, row in df.iterrows():
            if row['date'] >= alert_date:
                entry_idx = i
                break

        if entry_idx is None:
            logger.warning(f"Could not find entry date for {ticker}")
            return None

        # Get KC values at entry
        entry_row = df.loc[entry_idx]
        kc_lower = entry_row['kc_lower']
        kc_middle = entry_row['kc_middle']
        kc_upper = entry_row['kc_upper']

        # Calculate position size
        position_value = self.initial_capital * (self.position_size_pct / 100)
        quantity = int(position_value / entry_price)
        actual_value = quantity * entry_price

        if quantity == 0:
            return None

        # Simulate day by day from entry
        exit_date = None
        exit_price = None
        exit_reason = None

        df_from_entry = df.loc[entry_idx:]

        for i, (idx, row) in enumerate(df_from_entry.iterrows()):
            if i == 0:
                continue  # Skip entry day

            current_low = row['low']
            current_close = row['close']
            current_kc_lower = row['kc_lower']
            current_kc_middle = row['kc_middle']

            # Check exit condition based on strategy
            if exit_type == 'kc_lower':
                # Exit if low breaches KC Lower
                if current_low <= current_kc_lower:
                    exit_date = str(row['date'])
                    exit_price = current_kc_lower  # Exit at KC Lower
                    exit_reason = 'KC_LOWER_BREACH'
                    break
            elif exit_type == 'kc_middle':
                # Exit if low breaches KC Middle (SMA20)
                if current_low <= current_kc_middle:
                    exit_date = str(row['date'])
                    exit_price = current_kc_middle  # Exit at KC Middle
                    exit_reason = 'KC_MIDDLE_BREACH'
                    break

        # If still holding, use current price
        if exit_date is None:
            last_row = df.iloc[-1]
            exit_date = str(last_row['date'])
            exit_price = last_row['close']
            exit_reason = 'STILL_HOLDING'

        # Calculate P&L
        gross_pnl = (exit_price - entry_price) * quantity
        entry_charges = actual_value * (self.charges_per_leg_pct / 100)
        exit_charges = (exit_price * quantity) * (self.charges_per_leg_pct / 100)
        net_pnl = gross_pnl - entry_charges - exit_charges
        pnl_pct = (net_pnl / actual_value) * 100

        # Days held
        try:
            entry_dt = datetime.strptime(str(alert_date), '%Y-%m-%d')
            exit_dt = datetime.strptime(exit_date, '%Y-%m-%d')
            days_held = (exit_dt - entry_dt).days
        except:
            days_held = 0

        return Position(
            ticker=ticker,
            entry_date=str(alert_date),
            entry_price=entry_price,
            quantity=quantity,
            position_value=actual_value,
            kc_lower=round(kc_lower, 2),
            kc_middle=round(kc_middle, 2),
            kc_upper=round(kc_upper, 2),
            exit_date=exit_date,
            exit_price=round(exit_price, 2),
            exit_reason=exit_reason,
            pnl=round(net_pnl, 2),
            pnl_pct=round(pnl_pct, 2),
            days_held=days_held
        )

    def run_backtest(self, exit_type: str) -> SimulationResult:
        """
        Run backtest simulation

        Args:
            exit_type: 'kc_lower' or 'kc_middle'

        Returns:
            SimulationResult with all metrics
        """
        sim_name = "Sim 1: KC Lower Exit" if exit_type == 'kc_lower' else "Sim 2: KC Middle Exit"
        logger.info(f"Running backtest: {sim_name}")

        alerts = self.get_telegram_alerts()
        if not alerts:
            logger.error("No alerts found")
            return None

        positions = []
        total_charges = 0

        for i, alert in enumerate(alerts):
            pos = self.simulate_position(alert, exit_type)
            if pos:
                positions.append(pos)
                # Accumulate charges
                entry_charges = pos.position_value * (self.charges_per_leg_pct / 100)
                exit_charges = (pos.exit_price * pos.quantity) * (self.charges_per_leg_pct / 100)
                total_charges += entry_charges + exit_charges

            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(alerts)} alerts")

        if not positions:
            logger.error("No positions simulated")
            return None

        # Calculate metrics
        total_pnl = sum(p.pnl for p in positions)
        winning = [p for p in positions if p.pnl > 0]
        losing = [p for p in positions if p.pnl < 0]

        result = SimulationResult(
            sim_name=sim_name,
            exit_strategy=exit_type,
            initial_capital=self.initial_capital,
            final_capital=self.initial_capital + total_pnl,
            total_pnl=total_pnl,
            total_pnl_pct=(total_pnl / self.initial_capital) * 100,
            total_trades=len(positions),
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=(len(winning) / len(positions) * 100) if positions else 0,
            avg_win=np.mean([p.pnl for p in winning]) if winning else 0,
            avg_loss=np.mean([p.pnl for p in losing]) if losing else 0,
            max_win=max([p.pnl for p in winning]) if winning else 0,
            max_loss=min([p.pnl for p in losing]) if losing else 0,
            avg_days_held=np.mean([p.days_held for p in positions]),
            total_charges=total_charges,
            positions=positions
        )

        return result

    def generate_report(self, result: SimulationResult, filename: str):
        """Generate Excel report for simulation result"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Simulation Results"

        # Header styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")

        # Summary section
        summary_data = [
            ["SIMULATION BACKTEST RESULTS", ""],
            ["", ""],
            ["Simulation", result.sim_name],
            ["Exit Strategy", result.exit_strategy.upper()],
            ["Lookback Period", f"{self.lookback_days} days"],
            ["", ""],
            ["CAPITAL", ""],
            ["Initial Capital", f"₹{result.initial_capital:,.0f}"],
            ["Final Capital", f"₹{result.final_capital:,.0f}"],
            ["Total P&L", f"₹{result.total_pnl:,.0f}"],
            ["Return %", f"{result.total_pnl_pct:.2f}%"],
            ["", ""],
            ["TRADE STATISTICS", ""],
            ["Total Trades", result.total_trades],
            ["Winning Trades", result.winning_trades],
            ["Losing Trades", result.losing_trades],
            ["Win Rate", f"{result.win_rate:.1f}%"],
            ["Avg Win", f"₹{result.avg_win:,.0f}"],
            ["Avg Loss", f"₹{result.avg_loss:,.0f}"],
            ["Max Win", f"₹{result.max_win:,.0f}"],
            ["Max Loss", f"₹{result.max_loss:,.0f}"],
            ["Avg Days Held", f"{result.avg_days_held:.1f}"],
            ["Total Charges", f"₹{result.total_charges:,.0f}"],
        ]

        for row in summary_data:
            ws.append(row)

        # Add blank rows
        ws.append([])
        ws.append([])

        # Trades detail header
        trades_header = ["Ticker", "Entry Date", "Entry Price", "KC Lower", "KC Middle",
                        "Exit Date", "Exit Price", "Exit Reason", "Quantity", "P&L", "P&L %", "Days Held"]

        header_row = ws.max_row + 1
        for col, header in enumerate(trades_header, 1):
            cell = ws.cell(row=header_row, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill

        # Add trades
        for pos in result.positions:
            ws.append([
                pos.ticker,
                pos.entry_date,
                pos.entry_price,
                pos.kc_lower,
                pos.kc_middle,
                pos.exit_date,
                pos.exit_price,
                pos.exit_reason,
                pos.quantity,
                pos.pnl,
                pos.pnl_pct,
                pos.days_held
            ])

        # Format P&L columns with colors
        for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
            pnl_cell = row[9]  # P&L column
            if isinstance(pnl_cell.value, (int, float)):
                if pnl_cell.value > 0:
                    pnl_cell.font = Font(color="008000", bold=True)
                elif pnl_cell.value < 0:
                    pnl_cell.font = Font(color="FF0000")

        # Adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws.column_dimensions[column_letter].width = min(max_length + 2, 20)

        filepath = self.output_dir / filename
        wb.save(filepath)
        logger.info(f"Report saved: {filepath}")
        return filepath


def main():
    """Run backtests for both strategies"""
    import argparse

    parser = argparse.ArgumentParser(description='Telegram Alert Backtester')
    parser.add_argument('--days', type=int, default=10, help='Lookback days (default: 10)')
    parser.add_argument('--capital', type=float, default=10000000, help='Initial capital (default: 1 Cr)')
    parser.add_argument('--position-size', type=float, default=5.0, help='Position size % (default: 5)')
    args = parser.parse_args()

    backtester = TelegramAlertBacktester(
        initial_capital=args.capital,
        position_size_pct=args.position_size,
        lookback_days=args.days
    )

    print("\n" + "=" * 70)
    print("TELEGRAM ALERT BACKTESTER")
    print(f"Capital: ₹{args.capital:,.0f} | Position Size: {args.position_size}% | Lookback: {args.days} days")
    print("=" * 70)

    # Run Sim 1: KC Lower Exit
    print("\n[1/2] Running Sim 1: KC Lower Exit...")
    result1 = backtester.run_backtest('kc_lower')

    # Run Sim 2: KC Middle Exit
    print("\n[2/2] Running Sim 2: KC Middle Exit...")
    result2 = backtester.run_backtest('kc_middle')

    # Generate reports
    today = datetime.now().strftime('%Y%m%d')

    if result1:
        backtester.generate_report(result1, f"Backtest_Sim1_KC_Lower_{today}.xlsx")

    if result2:
        backtester.generate_report(result2, f"Backtest_Sim2_KC_Middle_{today}.xlsx")

    # Print comparison
    print("\n" + "=" * 70)
    print("BACKTEST RESULTS COMPARISON")
    print("=" * 70)

    if result1 and result2:
        print(f"\n{'Metric':<25} {'Sim 1 (KC Lower)':<20} {'Sim 2 (KC Middle)':<20}")
        print("-" * 65)
        print(f"{'Total Trades':<25} {result1.total_trades:<20} {result2.total_trades:<20}")
        print(f"{'Win Rate':<25} {result1.win_rate:.1f}%{'':<17} {result2.win_rate:.1f}%")
        print(f"{'Total P&L':<25} ₹{result1.total_pnl:>15,.0f} ₹{result2.total_pnl:>15,.0f}")
        print(f"{'Return %':<25} {result1.total_pnl_pct:>15.2f}% {result2.total_pnl_pct:>15.2f}%")
        print(f"{'Avg Days Held':<25} {result1.avg_days_held:>15.1f} {result2.avg_days_held:>15.1f}")
        print(f"{'Max Win':<25} ₹{result1.max_win:>15,.0f} ₹{result2.max_win:>15,.0f}")
        print(f"{'Max Loss':<25} ₹{result1.max_loss:>15,.0f} ₹{result2.max_loss:>15,.0f}")
        print(f"{'Total Charges':<25} ₹{result1.total_charges:>15,.0f} ₹{result2.total_charges:>15,.0f}")

        # Winner
        print("\n" + "-" * 65)
        if result1.total_pnl > result2.total_pnl:
            print(f"WINNER: Sim 1 (KC Lower) by ₹{result1.total_pnl - result2.total_pnl:,.0f}")
        elif result2.total_pnl > result1.total_pnl:
            print(f"WINNER: Sim 2 (KC Middle) by ₹{result2.total_pnl - result1.total_pnl:,.0f}")
        else:
            print("TIE: Both strategies performed equally")

    print("\n" + "=" * 70)
    print(f"Reports saved to: {backtester.output_dir}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
