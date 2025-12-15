"""
Excel Exporter for Simulation Results
Exports trades, portfolio snapshots, and statistics to Excel for analysis
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from .database_manager import SimulationDatabase

logger = logging.getLogger(__name__)


class SimulationExcelExporter:
    """Export simulation results to Excel files"""

    def __init__(self, output_dir: Optional[Path] = None):
        if output_dir is None:
            output_dir = Path(__file__).parent.parent / 'results'
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def export_simulation(self, sim_id: str, include_signals: bool = True) -> str:
        """
        Export a single simulation to Excel

        Returns the path to the exported file
        """
        db = SimulationDatabase(sim_id)

        # Get all data
        all_trades = db.get_all_trades()
        open_trades = db.get_open_trades()
        closed_trades = db.get_closed_trades(limit=10000)
        daily_snapshots = db.get_daily_snapshots(limit=100)
        stats = db.get_statistics()
        portfolio_state = db.get_current_portfolio_state()

        # Create DataFrames
        trades_df = pd.DataFrame(all_trades) if all_trades else pd.DataFrame()
        open_df = pd.DataFrame(open_trades) if open_trades else pd.DataFrame()
        closed_df = pd.DataFrame(closed_trades) if closed_trades else pd.DataFrame()
        daily_df = pd.DataFrame(daily_snapshots) if daily_snapshots else pd.DataFrame()

        # Statistics summary
        stats_data = {
            'Metric': [
                'Total Trades',
                'Open Trades',
                'Closed Trades',
                'Winning Trades',
                'Losing Trades',
                'Win Rate (%)',
                'Total P&L',
                'Avg P&L per Trade',
                'Avg P&L %',
                'Max Win',
                'Max Loss',
                'Current Portfolio Value',
                'Cash',
                'Invested',
                'Total P&L %'
            ],
            'Value': [
                stats.get('total_trades', 0),
                stats.get('open_trades', 0),
                stats.get('closed_trades', 0),
                stats.get('winning_trades', 0),
                stats.get('losing_trades', 0),
                stats.get('win_rate', 0),
                stats.get('total_pnl', 0),
                stats.get('avg_pnl', 0),
                stats.get('avg_pnl_pct', 0),
                stats.get('max_win', 0),
                stats.get('max_loss', 0),
                portfolio_state.get('total_value', 0) if portfolio_state else 0,
                portfolio_state.get('cash', 0) if portfolio_state else 0,
                portfolio_state.get('invested', 0) if portfolio_state else 0,
                portfolio_state.get('total_pnl_pct', 0) if portfolio_state else 0
            ]
        }
        stats_df = pd.DataFrame(stats_data)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"simulation_{sim_id}_{timestamp}.xlsx"
        filepath = self.output_dir / filename

        # Write to Excel with multiple sheets
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            stats_df.to_excel(writer, sheet_name='Summary', index=False)

            if not trades_df.empty:
                trades_df.to_excel(writer, sheet_name='All Trades', index=False)

            if not open_df.empty:
                open_df.to_excel(writer, sheet_name='Open Positions', index=False)

            if not closed_df.empty:
                closed_df.to_excel(writer, sheet_name='Closed Trades', index=False)

            if not daily_df.empty:
                daily_df.to_excel(writer, sheet_name='Daily Snapshots', index=False)

        logger.info(f"Exported {sim_id} to {filepath}")
        return str(filepath)

    def export_all_simulations(self) -> str:
        """
        Export all 4 simulations to a single Excel file with multiple sheets

        Returns the path to the exported file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"all_simulations_{timestamp}.xlsx"
        filepath = self.output_dir / filename

        sim_configs = {
            'sim_1': 'Long_KC_Lower',
            'sim_2': 'Long_PSAR',
            'sim_3': 'Short_KC_Upper',
            'sim_4': 'Short_PSAR'
        }

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Summary comparison sheet
            summary_data = []

            for sim_id, sim_name in sim_configs.items():
                db = SimulationDatabase(sim_id)
                stats = db.get_statistics()
                portfolio = db.get_current_portfolio_state()

                summary_data.append({
                    'Simulation': sim_name,
                    'Total Trades': stats.get('total_trades', 0),
                    'Open Trades': stats.get('open_trades', 0),
                    'Closed Trades': stats.get('closed_trades', 0),
                    'Winning': stats.get('winning_trades', 0),
                    'Losing': stats.get('losing_trades', 0),
                    'Win Rate %': stats.get('win_rate', 0),
                    'Total P&L': stats.get('total_pnl', 0),
                    'Avg P&L': stats.get('avg_pnl', 0),
                    'Max Win': stats.get('max_win', 0),
                    'Max Loss': stats.get('max_loss', 0),
                    'Portfolio Value': portfolio.get('total_value', 10000000) if portfolio else 10000000,
                    'P&L %': portfolio.get('total_pnl_pct', 0) if portfolio else 0
                })

                # Individual simulation trades
                trades = db.get_all_trades()
                if trades:
                    trades_df = pd.DataFrame(trades)
                    trades_df.to_excel(writer, sheet_name=f'{sim_name}_Trades', index=False)

            # Write summary
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Comparison', index=False)

        logger.info(f"Exported all simulations to {filepath}")
        return str(filepath)

    def export_daily_report(self) -> str:
        """
        Export daily report for all simulations

        Returns the path to the exported file
        """
        today = datetime.now().strftime('%Y%m%d')
        filename = f"daily_report_{today}.xlsx"
        filepath = self.output_dir / filename

        sim_configs = {
            'sim_1': 'Long_KC_Lower',
            'sim_2': 'Long_PSAR',
            'sim_3': 'Short_KC_Upper',
            'sim_4': 'Short_PSAR'
        }

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            all_trades_today = []

            for sim_id, sim_name in sim_configs.items():
                db = SimulationDatabase(sim_id)

                # Get today's trades
                all_trades = db.get_all_trades()
                today_str = datetime.now().strftime('%Y-%m-%d')

                for trade in all_trades:
                    entry_ts = trade.get('entry_timestamp', '')
                    if entry_ts and entry_ts.startswith(today_str):
                        trade['simulation'] = sim_name
                        all_trades_today.append(trade)

            if all_trades_today:
                daily_df = pd.DataFrame(all_trades_today)
                daily_df.to_excel(writer, sheet_name='Today_Trades', index=False)

            # Summary
            summary_data = []
            for sim_id, sim_name in sim_configs.items():
                db = SimulationDatabase(sim_id)
                stats = db.get_statistics()
                portfolio = db.get_current_portfolio_state()

                summary_data.append({
                    'Simulation': sim_name,
                    'Portfolio Value': portfolio.get('total_value', 10000000) if portfolio else 10000000,
                    'P&L': portfolio.get('total_pnl', 0) if portfolio else 0,
                    'P&L %': portfolio.get('total_pnl_pct', 0) if portfolio else 0,
                    'Open Positions': stats.get('open_trades', 0),
                    'Win Rate %': stats.get('win_rate', 0)
                })

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        logger.info(f"Exported daily report to {filepath}")
        return str(filepath)


def export_to_excel(sim_id: str = None) -> str:
    """
    Quick export function

    If sim_id is provided, exports that simulation.
    Otherwise exports all simulations.
    """
    exporter = SimulationExcelExporter()

    if sim_id:
        return exporter.export_simulation(sim_id)
    else:
        return exporter.export_all_simulations()


if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description='Export Simulation Results to Excel')
    parser.add_argument('--sim-id', help='Simulation ID (sim_1, sim_2, sim_3, sim_4)')
    parser.add_argument('--all', action='store_true', help='Export all simulations')
    parser.add_argument('--daily', action='store_true', help='Export daily report')
    args = parser.parse_args()

    exporter = SimulationExcelExporter()

    if args.daily:
        path = exporter.export_daily_report()
    elif args.all or not args.sim_id:
        path = exporter.export_all_simulations()
    else:
        path = exporter.export_simulation(args.sim_id)

    print(f"Exported to: {path}")
