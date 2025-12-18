"""
Simulation Dashboard
Web dashboard for displaying simulation results and performance metrics
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from flask import Flask, render_template_string, jsonify, request

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.database_manager import SimulationDatabase

logger = logging.getLogger(__name__)


def fetch_current_prices(tickers: List[str]) -> Dict[str, float]:
    """Fetch current prices for a list of tickers from Kite API"""
    if not tickers:
        return {}

    prices = {}
    try:
        import configparser
        from kiteconnect import KiteConnect

        # Load credentials from config.ini (same as keltner_calculator)
        config = configparser.ConfigParser()
        config_path = Path(__file__).parent.parent.parent / 'config.ini'
        config.read(config_path)

        credential_section = 'API_CREDENTIALS_Sai'
        api_key = config.get(credential_section, 'api_key')
        access_token = config.get(credential_section, 'access_token')

        kite = KiteConnect(api_key=api_key)
        kite.set_access_token(access_token)

        symbols = [f"NSE:{t}" for t in tickers]
        ltp_data = kite.ltp(symbols)

        for symbol, data in ltp_data.items():
            ticker = symbol.replace("NSE:", "")
            prices[ticker] = data.get('last_price', 0)

    except Exception as e:
        logger.warning(f"Could not fetch real-time prices: {e}")
        # Return empty dict, caller will use entry prices

    return prices

# Dashboard HTML template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>{{ sim_name }} - VSR Simulation Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #0f3460;
        }
        .header h1 {
            color: #e94560;
            font-size: 1.8em;
        }
        .header .meta {
            text-align: right;
            font-size: 0.9em;
            color: #888;
        }
        .sim-id { color: #4ecca3; font-weight: bold; }

        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 20px; }

        .card {
            background: rgba(15, 52, 96, 0.5);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #0f3460;
        }
        .card h3 {
            color: #4ecca3;
            margin-bottom: 15px;
            font-size: 1em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #888; }
        .metric-value { font-weight: bold; font-size: 1.1em; }

        .positive { color: #4ecca3; }
        .negative { color: #e94560; }
        .neutral { color: #ffd93d; }

        .big-number {
            font-size: 2.5em;
            font-weight: bold;
            text-align: center;
            padding: 20px;
        }
        .big-label {
            text-align: center;
            color: #888;
            font-size: 0.9em;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th {
            background: rgba(0,0,0,0.2);
            color: #4ecca3;
            font-weight: normal;
            text-transform: uppercase;
            font-size: 0.85em;
        }
        tr:hover { background: rgba(255,255,255,0.05); }

        .status-badge {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-open { background: #4ecca3; color: #000; }
        .status-closed { background: #888; color: #fff; }
        .status-pending { background: #ffd93d; color: #000; }

        .pnl-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }
        .pnl-bar-fill {
            height: 100%;
            transition: width 0.3s;
        }
        .pnl-bar-positive { background: #4ecca3; }
        .pnl-bar-negative { background: #e94560; }

        .daily-chart {
            display: flex;
            align-items: flex-end;
            height: 100px;
            gap: 4px;
            padding: 10px 0;
        }
        .daily-bar {
            flex: 1;
            min-width: 20px;
            border-radius: 2px 2px 0 0;
            transition: height 0.3s;
        }
        .daily-bar-positive { background: #4ecca3; }
        .daily-bar-negative { background: #e94560; }

        .footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.85em;
        }

        .refresh-btn {
            background: #4ecca3;
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }
        .refresh-btn:hover { background: #3db892; }

        .position-row td:first-child { color: #4ecca3; font-weight: bold; }

        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            .header { flex-direction: column; text-align: center; }
            .header .meta { margin-top: 10px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ sim_name }}</h1>
        <div class="meta">
            <div>Simulation ID: <span class="sim-id">{{ sim_id }}</span></div>
            <div>Port: {{ port }}</div>
            <div>Started: <span style="color: #4ecca3;">{{ simulation_started }}</span></div>
            <div>Last Updated: {{ last_updated }}</div>
            <button class="refresh-btn" onclick="location.reload()">Refresh</button>
        </div>
    </div>

    <!-- Portfolio Overview -->
    <div class="grid">
        <div class="card">
            <h3>Portfolio Value</h3>
            <div class="big-number {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                ₹{{ "{:,.0f}".format(current_value) }}
            </div>
            <div class="big-label">Initial: ₹{{ "{:,.0f}".format(initial_capital) }}</div>
        </div>

        <div class="card">
            <h3>Total P&L</h3>
            <div class="big-number {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                {{ "+" if total_pnl >= 0 else "" }}₹{{ "{:,.0f}".format(total_pnl) }}
            </div>
            <div class="big-label">{{ "{:+.2f}".format(total_pnl_pct) }}%</div>
        </div>

        <div class="card">
            <h3>Win Rate</h3>
            <div class="big-number {{ 'positive' if win_rate >= 50 else 'negative' }}">
                {{ "{:.1f}".format(win_rate) }}%
            </div>
            <div class="big-label">{{ winning_trades }}W / {{ losing_trades }}L</div>
        </div>

        <div class="card">
            <h3>Open Positions</h3>
            <div class="big-number neutral">
                {{ open_positions }}
            </div>
            <div class="big-label">Max: {{ max_positions }}</div>
        </div>
    </div>

    <!-- Detailed Metrics -->
    <div class="grid">
        <div class="card">
            <h3>Capital Breakdown</h3>
            <div class="metric">
                <span class="metric-label">Cash Available</span>
                <span class="metric-value">₹{{ "{:,.0f}".format(cash) }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Invested</span>
                <span class="metric-value">₹{{ "{:,.0f}".format(invested) }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Realized P&L</span>
                <span class="metric-value {{ 'positive' if realized_pnl >= 0 else 'negative' }}">
                    {{ "+" if realized_pnl >= 0 else "" }}₹{{ "{:,.0f}".format(realized_pnl) }}
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Unrealized P&L</span>
                <span class="metric-value {{ 'positive' if unrealized_pnl >= 0 else 'negative' }}">
                    {{ "+" if unrealized_pnl >= 0 else "" }}₹{{ "{:,.0f}".format(unrealized_pnl) }}
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Total Charges Paid</span>
                <span class="metric-value negative">-₹{{ "{:,.0f}".format(total_charges) }}</span>
            </div>
        </div>

        <div class="card">
            <h3>Trade Statistics</h3>
            <div class="metric">
                <span class="metric-label">Total Trades</span>
                <span class="metric-value">{{ total_trades }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Closed Trades</span>
                <span class="metric-value">{{ closed_trades }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Average P&L</span>
                <span class="metric-value {{ 'positive' if avg_pnl >= 0 else 'negative' }}">
                    ₹{{ "{:,.0f}".format(avg_pnl) }}
                </span>
            </div>
            <div class="metric">
                <span class="metric-label">Best Trade</span>
                <span class="metric-value positive">₹{{ "{:,.0f}".format(max_win) }}</span>
            </div>
            <div class="metric">
                <span class="metric-label">Worst Trade</span>
                <span class="metric-value negative">₹{{ "{:,.0f}".format(max_loss) }}</span>
            </div>
        </div>

        <div class="card">
            <h3>Risk Metrics</h3>
            <div class="metric">
                <span class="metric-label">Max Drawdown</span>
                <span class="metric-value negative">{{ "{:.2f}".format(max_drawdown) }}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Position Size</span>
                <span class="metric-value">{{ position_size_pct }}%</span>
            </div>
            <div class="metric">
                <span class="metric-label">Charges/Leg</span>
                <span class="metric-value">{{ charges_per_leg }}%</span>
            </div>
        </div>
    </div>

    <!-- Open Positions -->
    <div class="card" style="margin-bottom: 20px;">
        <h3>Open Positions ({{ open_positions }})</h3>
        {% if positions %}
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Entry</th>
                    <th>Current</th>
                    <th>Qty</th>
                    <th>Value</th>
                    <th>P&L</th>
                    <th>Stop Loss</th>
                    <th>Target (9%)</th>
                </tr>
            </thead>
            <tbody>
                {% for pos in positions %}
                <tr class="position-row">
                    <td>{{ pos.ticker }}</td>
                    <td>₹{{ "{:.2f}".format(pos.entry_price) }}</td>
                    <td>₹{{ "{:.2f}".format(pos.current_price) }}</td>
                    <td>{{ pos.quantity }}</td>
                    <td>₹{{ "{:,.0f}".format(pos.entry_price * pos.quantity) }}</td>
                    <td class="{{ 'positive' if pos.unrealized_pnl >= 0 else 'negative' }}">
                        {{ "+" if pos.unrealized_pnl >= 0 else "" }}₹{{ "{:,.0f}".format(pos.unrealized_pnl) }}
                        ({{ "{:+.1f}".format(pos.unrealized_pnl_pct) }}%)
                    </td>
                    <td class="negative">₹{{ "{:.2f}".format(pos.stop_loss) }}</td>
                    <td class="positive">₹{{ "{:.2f}".format(pos.target) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="text-align: center; color: #666; padding: 20px;">No open positions</p>
        {% endif %}
    </div>

    <!-- Recent Trades -->
    <div class="card">
        <h3>Recent Closed Trades</h3>
        {% if recent_trades %}
        <table>
            <thead>
                <tr>
                    <th>Ticker</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th>Qty</th>
                    <th>P&L</th>
                    <th>Exit Reason</th>
                    <th>Exit Time</th>
                </tr>
            </thead>
            <tbody>
                {% for trade in recent_trades %}
                <tr>
                    <td style="color: #4ecca3; font-weight: bold;">{{ trade.ticker }}</td>
                    <td>₹{{ "{:.2f}".format(trade.entry_price or 0) }}</td>
                    <td>₹{{ "{:.2f}".format(trade.exit_price or 0) }}</td>
                    <td>{{ trade.quantity or 0 }}</td>
                    <td class="{{ 'positive' if (trade.pnl or 0) >= 0 else 'negative' }}">
                        {{ "+" if (trade.pnl or 0) >= 0 else "" }}₹{{ "{:,.0f}".format(trade.pnl or 0) }}
                        ({{ "{:+.1f}".format(trade.pnl_pct or 0) }}%)
                    </td>
                    <td>
                        <span class="status-badge {{ 'status-closed' if trade.exit_reason == 'STOP_LOSS' else 'status-open' }}">
                            {{ trade.exit_reason or 'N/A' }}
                        </span>
                    </td>
                    <td>{{ (trade.exit_timestamp or '')[:16] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p style="text-align: center; color: #666; padding: 20px;">No closed trades yet</p>
        {% endif %}
    </div>

    <div class="footer">
        <p>VSR Trading Simulation | Auto-refresh every 60 seconds</p>
        <p>{{ description }}</p>
    </div>
</body>
</html>
"""


def get_first_trade_timestamp(sim_id: str) -> Optional[str]:
    """Get the timestamp of the first trade for this simulation"""
    try:
        db_path = Path(__file__).parent.parent / "data" / f"simulation_{sim_id}.db"
        if not db_path.exists():
            return None

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT MIN(entry_timestamp) FROM trades WHERE entry_timestamp IS NOT NULL")
        result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            # Parse and reformat to consistent format
            ts = result[0]
            # Handle various timestamp formats
            if 'T' in ts:
                ts = ts.replace('T', ' ')
            return ts[:19]  # Return YYYY-MM-DD HH:MM:SS format
        return None
    except Exception as e:
        logger.warning(f"Could not get first trade timestamp: {e}")
        return None


def create_dashboard_app(sim_id: str, config: Dict) -> Flask:
    """Create Flask app for a simulation dashboard"""
    app = Flask(__name__)
    app.config['sim_id'] = sim_id
    app.config['sim_config'] = config

    sim_config = config.get('simulations', {}).get(sim_id, {})
    global_config = config.get('global', {})

    db = SimulationDatabase(sim_id)

    @app.route('/')
    def index():
        # Get current data
        portfolio_state = db.get_current_portfolio_state() or {}
        stats = db.get_statistics()
        open_trades = db.get_open_trades()
        closed_trades = db.get_closed_trades(limit=20)

        # Fetch current prices for all open positions
        open_tickers = [t['ticker'] for t in open_trades if t.get('ticker')]
        current_prices = fetch_current_prices(open_tickers)

        # Get direction from sim_config
        direction = sim_config.get('direction', 'long')

        # Get charges rate from config
        charges_per_leg_pct = sim_config.get('charges_per_leg_pct', 0.15)

        # Build positions list with real-time prices
        positions = []
        total_unrealized_pnl = 0
        total_invested = 0
        for trade in open_trades:
            ticker = trade['ticker']
            entry_price = trade['entry_price'] or 0
            quantity = trade['quantity'] or 0
            current_price = current_prices.get(ticker, entry_price)

            # Calculate unrealized P&L based on direction
            if direction == 'long':
                unrealized_pnl = (current_price - entry_price) * quantity
            else:  # short
                unrealized_pnl = (entry_price - current_price) * quantity

            position_value = entry_price * quantity
            total_invested += position_value
            unrealized_pnl_pct = (unrealized_pnl / position_value * 100) if position_value > 0 else 0
            total_unrealized_pnl += unrealized_pnl

            positions.append({
                'ticker': ticker,
                'entry_price': entry_price,
                'current_price': current_price,
                'quantity': quantity,
                'unrealized_pnl': unrealized_pnl,
                'unrealized_pnl_pct': unrealized_pnl_pct,
                'stop_loss': trade['stop_loss'] or 0,
                'target': trade['target'] or (entry_price * 1.09 if direction == 'long' else entry_price * 0.91)
            })

        # Calculate total charges paid (entry charges for open positions)
        # Entry charges = invested_value × charges_per_leg_pct / 100
        total_entry_charges = total_invested * (charges_per_leg_pct / 100)

        # Add exit charges from closed trades (approximation: same as entry charges)
        total_closed_value = sum(
            (t.get('entry_price', 0) or 0) * (t.get('quantity', 0) or 0)
            for t in closed_trades
        )
        total_exit_charges = total_closed_value * (charges_per_leg_pct / 100) * 2  # Entry + Exit

        total_charges = total_entry_charges + total_exit_charges

        return render_template_string(
            DASHBOARD_HTML,
            sim_id=sim_id,
            sim_name=sim_config.get('name', f'Simulation {sim_id}'),
            port=sim_config.get('port', 4001),
            description=sim_config.get('description', ''),
            simulation_started=get_first_trade_timestamp(sim_id) or "No trades yet",
            last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

            # Portfolio metrics
            initial_capital=global_config.get('initial_capital', 10000000),
            current_value=portfolio_state.get('total_value', global_config.get('initial_capital', 10000000)),
            cash=portfolio_state.get('cash', global_config.get('initial_capital', 10000000)),
            invested=portfolio_state.get('invested', 0),
            realized_pnl=stats.get('total_pnl', 0),
            unrealized_pnl=total_unrealized_pnl,
            total_pnl=stats.get('total_pnl', 0) + total_unrealized_pnl,
            total_pnl_pct=portfolio_state.get('total_pnl_pct', 0),
            total_charges=total_charges,

            # Trade stats
            total_trades=stats.get('total_trades', 0),
            closed_trades=stats.get('closed_trades', 0),
            open_positions=stats.get('open_trades', 0),
            max_positions=global_config.get('max_positions', 20),
            winning_trades=stats.get('winning_trades', 0),
            losing_trades=stats.get('losing_trades', 0),
            win_rate=stats.get('win_rate', 0),
            avg_pnl=stats.get('avg_pnl', 0),
            max_win=stats.get('max_win', 0),
            max_loss=stats.get('max_loss', 0),

            # Risk
            max_drawdown=0,  # TODO: Track
            position_size_pct=global_config.get('position_size_pct', 5),
            charges_per_leg=global_config.get('charges_per_leg_pct', 0.15),

            # Positions and trades
            positions=positions,
            recent_trades=closed_trades
        )

    @app.route('/api/summary')
    def api_summary():
        """API endpoint for portfolio summary"""
        portfolio_state = db.get_current_portfolio_state() or {}
        stats = db.get_statistics()
        return jsonify({
            'sim_id': sim_id,
            'portfolio': portfolio_state,
            'statistics': stats,
            'timestamp': datetime.now().isoformat()
        })

    @app.route('/api/positions')
    def api_positions():
        """API endpoint for open positions"""
        return jsonify(db.get_open_trades())

    @app.route('/api/trades')
    def api_trades():
        """API endpoint for all trades"""
        limit = request.args.get('limit', 100, type=int)
        return jsonify(db.get_closed_trades(limit=limit))

    @app.route('/api/daily')
    def api_daily():
        """API endpoint for daily snapshots"""
        return jsonify(db.get_daily_snapshots())

    return app


def run_dashboard(sim_id: str, port: int = 4001):
    """Run dashboard for a specific simulation"""
    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'simulation_config.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    app = create_dashboard_app(sim_id, config)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info(f"Starting dashboard for {sim_id} on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run Simulation Dashboard')
    parser.add_argument('--sim-id', default='sim_1', help='Simulation ID')
    parser.add_argument('--port', type=int, default=4001, help='Port number')
    args = parser.parse_args()

    run_dashboard(args.sim_id, args.port)
