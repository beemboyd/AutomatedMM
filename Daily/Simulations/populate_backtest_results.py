#!/usr/bin/env python3
"""
Populate Simulation Databases with Backtest Results

Loads backtest results from Excel files and populates the simulation databases
so they can be displayed on the dashboards.
"""

import sys
import sqlite3
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from core.database_manager import SimulationDatabase


def populate_simulation(sim_id: str, excel_path: str, initial_capital: float = 10000000):
    """
    Populate a simulation database with backtest results

    Args:
        sim_id: Simulation ID (sim_1 or sim_2)
        excel_path: Path to backtest Excel file
        initial_capital: Initial capital for the simulation
    """
    print(f"\nPopulating {sim_id} from {excel_path}")

    # Read Excel file - new format has multiple sheets
    try:
        # Read Open Positions sheet
        open_positions_df = pd.read_excel(excel_path, sheet_name='Open Positions')
        open_positions_df = open_positions_df[open_positions_df['Ticker'].notna()].copy()
        print(f"  Found {len(open_positions_df)} open positions")
    except Exception as e:
        print(f"  No open positions sheet or error: {e}")
        open_positions_df = pd.DataFrame()

    try:
        # Read Trade History sheet (closed trades)
        trade_history_df = pd.read_excel(excel_path, sheet_name='Trade History')
        trade_history_df = trade_history_df[trade_history_df['Ticker'].notna()].copy()
        print(f"  Found {len(trade_history_df)} closed trades")
    except Exception as e:
        print(f"  No trade history sheet or error: {e}")
        trade_history_df = pd.DataFrame()

    # Initialize database
    db = SimulationDatabase(sim_id)

    # Reset the simulation first
    db.reset_simulation()
    print(f"  Reset {sim_id} database")

    # Insert trades into database
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    position_value = initial_capital * 0.05  # 5% position size
    total_pnl = 0.0
    total_charges = 0.0

    # Insert closed trades
    for _, row in trade_history_df.iterrows():
        ticker = row['Ticker']
        entry_date = str(row['Entry Date'])
        entry_price = float(row['Entry Price'])
        exit_price = float(row['Exit Price'])
        exit_reason = row['Exit Reason']
        pnl = float(row['P&L'])
        pnl_pct = float(row['P&L %']) if 'P&L %' in row else 0
        days_held = int(row['Days Held']) if 'Days Held' in row else 0
        overnight_charges = float(row.get('Overnight Charges', 0))

        # Calculate quantity
        quantity = int(position_value / entry_price) if entry_price > 0 else 0
        if pnl_pct == 0 and quantity > 0:
            pnl_pct = (pnl / (entry_price * quantity)) * 100

        total_pnl += pnl

        # Extract KC values (use defaults if not available)
        kc_lower = entry_price * 0.95
        kc_middle = entry_price * 0.97
        kc_upper = entry_price * 1.05

        # Insert trade
        cursor.execute("""
            INSERT INTO trades (
                ticker, signal_price, signal_timestamp,
                entry_price, entry_timestamp, quantity,
                stop_loss, target, kc_lower, kc_upper, kc_middle,
                exit_price, exit_timestamp, exit_reason,
                pnl, pnl_pct, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            entry_price,  # signal_price
            entry_date,   # signal_timestamp
            entry_price,
            entry_date,   # entry_timestamp
            quantity,
            kc_lower if sim_id == 'sim_1' else kc_middle,  # stop_loss
            entry_price * 1.09,  # target (9%)
            kc_lower,
            kc_upper,
            kc_middle,
            exit_price,
            str(row.get('Exit Date', entry_date)) if 'Exit Date' in row else entry_date,
            exit_reason,
            pnl,
            pnl_pct,
            'CLOSED'
        ))

    # Insert open positions
    for _, row in open_positions_df.iterrows():
        ticker = row['Ticker']
        entry_date = str(row['Entry Date'])
        entry_price = float(row['Entry Price'])
        current_price = float(row['Current Price']) if 'Current Price' in row else entry_price
        quantity = int(row['Quantity']) if 'Quantity' in row else int(position_value / entry_price)
        unrealized_pnl = float(row['Unrealized P&L']) if 'Unrealized P&L' in row else 0
        unrealized_pnl_pct = float(row['P&L %']) if 'P&L %' in row else 0
        stop_loss = float(row['Stop Loss']) if 'Stop Loss' in row else entry_price * 0.95
        kc_lower = float(row['KC Lower']) if 'KC Lower' in row else entry_price * 0.95
        kc_middle = float(row['KC Middle']) if 'KC Middle' in row else entry_price * 0.97
        kc_upper = kc_middle * 1.1

        total_pnl += unrealized_pnl

        # Insert as open trade
        cursor.execute("""
            INSERT INTO trades (
                ticker, signal_price, signal_timestamp,
                entry_price, entry_timestamp, quantity,
                stop_loss, target, kc_lower, kc_upper, kc_middle,
                exit_price, exit_timestamp, exit_reason,
                pnl, pnl_pct, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            entry_price,  # signal_price
            entry_date,   # signal_timestamp
            entry_price,
            entry_date,   # entry_timestamp
            quantity,
            stop_loss,
            entry_price * 1.09,  # target (9%)
            kc_lower,
            kc_upper,
            kc_middle,
            None,  # exit_price - not exited yet
            None,  # exit_timestamp
            None,  # exit_reason
            unrealized_pnl,
            unrealized_pnl_pct,
            'OPEN'
        ))

    conn.commit()

    # Calculate summary stats
    winning_trades = len(trade_history_df[trade_history_df['P&L'] > 0]) if len(trade_history_df) > 0 else 0
    losing_trades = len(trade_history_df[trade_history_df['P&L'] < 0]) if len(trade_history_df) > 0 else 0
    total_trades = len(trade_history_df) + len(open_positions_df)

    # Calculate invested amount for open positions
    invested = len(open_positions_df) * position_value

    # Update portfolio state
    cash = initial_capital + total_pnl - invested

    cursor.execute("""
        INSERT OR REPLACE INTO portfolio_state (
            id, timestamp, cash, invested, total_value, open_positions,
            daily_pnl, total_pnl, metadata
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        cash,
        invested,
        initial_capital + total_pnl,
        len(open_positions_df),
        total_pnl,
        total_pnl,
        f'{{"direction": "long", "closed_trades": {len(trade_history_df)}}}'
    ))

    conn.commit()
    conn.close()

    print(f"  Inserted {total_trades} trades ({len(trade_history_df)} closed, {len(open_positions_df)} open)")
    print(f"  Total P&L: Rs.{total_pnl:,.0f}")
    if len(trade_history_df) > 0:
        win_rate = winning_trades / len(trade_history_df) * 100
        print(f"  Win Rate: {winning_trades}/{len(trade_history_df)} ({win_rate:.1f}%)")
    print(f"  Open positions: {len(open_positions_df)}")


def main():
    """Populate both simulations with backtest results"""
    base_dir = Path(__file__).parent.parent / "analysis" / "Efficiency"

    # Find latest backtest files (check multiple patterns for Sim 1)
    sim1_files = list(base_dir.glob("Backtest_Sim1_TD_Tranche_*.xlsx"))
    if not sim1_files:
        sim1_files = list(base_dir.glob("Backtest_Sim1_TD_Strategy_*.xlsx"))
    if not sim1_files:
        sim1_files = list(base_dir.glob("Backtest_Sim1_KC_Lower_*.xlsx"))

    # Find latest backtest files (check multiple patterns for Sim 2)
    sim2_files = list(base_dir.glob("Backtest_Sim2_DeltaCVD_*.xlsx"))
    if not sim2_files:
        sim2_files = list(base_dir.glob("Backtest_Sim2_KC_Middle_*.xlsx"))

    if not sim1_files:
        print("No Sim 1 backtest file found. Run the backtester first.")
        return

    if not sim2_files:
        print("No Sim 2 backtest file found. Run the backtester first.")
        return

    # Use most recent files
    sim1_file = sorted(sim1_files)[-1]
    sim2_file = sorted(sim2_files)[-1]

    print("=" * 60)
    print("POPULATING SIMULATION DATABASES WITH BACKTEST RESULTS")
    print("=" * 60)

    # Populate sim_1
    populate_simulation('sim_1', str(sim1_file))

    # Populate sim_2
    populate_simulation('sim_2', str(sim2_file))

    print("\n" + "=" * 60)
    print("DONE - Start dashboards to view results:")
    print("  python3 Daily/Simulations/dashboards/run_dashboard_1.py")
    print("  python3 Daily/Simulations/dashboards/run_dashboard_2.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
