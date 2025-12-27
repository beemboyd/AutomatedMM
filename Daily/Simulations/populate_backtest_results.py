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

    # Read Excel file
    df = pd.read_excel(excel_path, skiprows=23, header=0)
    df = df[df['Ticker'].notna()].copy()

    print(f"  Found {len(df)} trades")

    # Initialize database
    db = SimulationDatabase(sim_id)

    # Reset the simulation first
    db.reset_simulation()
    print(f"  Reset {sim_id} database")

    # Calculate totals from trades
    total_pnl = df['P&L'].sum()
    total_trades = len(df)
    winning_trades = len(df[df['P&L'] > 0])
    losing_trades = len(df[df['P&L'] < 0])

    # Estimate charges (0.15% per leg, 2 legs per trade)
    position_value = initial_capital * 0.05  # 5% position size
    total_charges = total_trades * position_value * 0.003  # 0.3% round trip

    # Insert trades into database
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    for _, row in df.iterrows():
        ticker = row['Ticker']
        entry_date = str(row['Entry Date'])
        entry_price = float(row['Entry Price'])
        exit_price = float(row['Exit Price'])
        exit_reason = row['Exit Reason']
        pnl = float(row['P&L'])
        days_held = int(row['Days Held'])
        kc_lower = float(row['KC Lower'])
        kc_middle = float(row['KC Middle'])

        # Calculate quantity
        quantity = int(position_value / entry_price)
        pnl_pct = (pnl / (entry_price * quantity)) * 100 if quantity > 0 else 0

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
            kc_middle * 1.1,  # kc_upper estimate
            kc_middle,
            exit_price,
            str(row.get('Exit Date', entry_date)) if 'Exit Date' in row else entry_date,
            exit_reason,
            pnl,
            pnl_pct,
            'closed' if exit_reason != 'STILL_HOLDING' else 'open'
        ))

    conn.commit()

    # Update portfolio state
    cash = initial_capital + total_pnl - total_charges

    # Separate still holding positions
    still_holding = df[df['Exit Reason'] == 'STILL_HOLDING']
    invested = len(still_holding) * position_value

    cursor.execute("""
        INSERT OR REPLACE INTO portfolio_state (
            id, timestamp, cash, invested, total_value, open_positions,
            daily_pnl, total_pnl, metadata
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        cash - invested,  # Adjust for invested
        invested,
        cash,
        len(still_holding),
        total_pnl,
        total_pnl,
        f'{{"total_charges": {total_charges}, "direction": "long"}}'
    ))

    conn.commit()
    conn.close()

    print(f"  Inserted {total_trades} trades")
    print(f"  Total P&L: ₹{total_pnl:,.0f}")
    print(f"  Win Rate: {winning_trades}/{total_trades} ({winning_trades/total_trades*100:.1f}%)")
    print(f"  Open positions: {len(still_holding)}")


def main():
    """Populate both simulations with backtest results"""
    base_dir = Path(__file__).parent.parent / "analysis" / "Efficiency"

    # Find latest backtest files
    sim1_files = list(base_dir.glob("Backtest_Sim1_KC_Lower_*.xlsx"))
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
