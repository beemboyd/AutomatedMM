"""
TG Grid Bot Dashboard — Config + Monitor web UI on port 7777.

Features:
- Config management: Read/write TG/state/tg_config.json
- Process management: Launch/stop bot subprocesses, track PIDs
- State monitoring: Poll TG/state/{SYMBOL}_grid_state.json for each primary
- Self-contained: Single file, inline HTML/CSS/JS

Usage:
    python -m TG.dashboard --port 7777
"""

import argparse
import json
import os
import sys
import signal
import subprocess
import logging
from datetime import datetime
from typing import Dict, Optional

from flask import Flask, jsonify, request, Response

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(os.path.dirname(__file__), 'state')
CONFIG_FILE = os.path.join(STATE_DIR, 'tg_config.json')

# Default config template
_DEFAULT_CONFIG = {
    "secondary_symbol": "SPCENET",
    "xts_interactive_key": "59ec1c9e69270e5cd97108",
    "xts_interactive_secret": "Mjcd080@xT",
    "xts_root": "https://xts.myfindoc.com",
    "zerodha_user": "Sai",
    "primaries": [
        {
            "symbol": "TATSILV",
            "enabled": True,
            "auto_anchor": True,
            "anchor_price": 0,
            "grid_space": 0.01,
            "target": 0.03,
            "total_qty": 10,
            "subset_qty": 1,
            "hedge_ratio": 1,
            "partial_hedge_ratio": 1,
            "holdings_override": 1000,
            "product": "NRML",
            "poll_interval": 2.0,
        }
    ],
}

# Track running bot processes
_running_bots: Dict[str, subprocess.Popen] = {}


def _load_config() -> dict:
    """Load config from JSON file, or return defaults."""
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load config: %s", e)
    return _DEFAULT_CONFIG.copy()


def _save_config(config: dict):
    """Save config to JSON file with atomic write."""
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(config, f, indent=2)
    os.replace(tmp, CONFIG_FILE)
    logger.info("Config saved to %s", CONFIG_FILE)


def _load_state(symbol: str) -> dict:
    """Load the latest state JSON for a symbol."""
    path = os.path.join(STATE_DIR, f'{symbol}_grid_state.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load state for %s: %s", symbol, e)
        return {}


def _get_primary_config(config: dict, symbol: str) -> Optional[dict]:
    """Find primary config by symbol."""
    for p in config.get('primaries', []):
        if p.get('symbol') == symbol:
            return p
    return None


def _is_bot_running(symbol: str) -> bool:
    """Check if a bot process is running for a symbol."""
    proc = _running_bots.get(symbol)
    if proc is None:
        return False
    if proc.poll() is not None:
        # Process has exited
        del _running_bots[symbol]
        return False
    return True


def _start_bot(symbol: str, config: dict) -> bool:
    """Launch TG.run as subprocess for a primary symbol."""
    if _is_bot_running(symbol):
        logger.warning("Bot for %s is already running (PID=%d)", symbol, _running_bots[symbol].pid)
        return False

    primary = _get_primary_config(config, symbol)
    if not primary:
        logger.error("No config found for primary %s", symbol)
        return False

    cmd = [
        sys.executable, '-m', 'TG.run',
        '--symbol', symbol,
        '--pair-symbol', config.get('secondary_symbol', ''),
        '--hedge-ratio', str(primary.get('hedge_ratio', 0)),
        '--partial-hedge-ratio', str(primary.get('partial_hedge_ratio', 0)),
        '--grid-space', str(primary.get('grid_space', 0.01)),
        '--target', str(primary.get('target', 0.02)),
        '--total-qty', str(primary.get('total_qty', 1000)),
        '--subset-qty', str(primary.get('subset_qty', 300)),
        '--holdings', str(primary.get('holdings_override', -1)),
        '--product', primary.get('product', 'NRML'),
        '--interactive-key', config.get('xts_interactive_key', ''),
        '--interactive-secret', config.get('xts_interactive_secret', ''),
        '--user', config.get('zerodha_user', 'Sai'),
        '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
        '--poll-interval', str(primary.get('poll_interval', 2.0)),
    ]

    if primary.get('auto_anchor'):
        cmd.append('--auto-anchor')
    else:
        anchor = primary.get('anchor_price', 0)
        if anchor > 0:
            cmd.extend(['--anchor', str(anchor)])
        else:
            cmd.append('--auto-anchor')

    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'{symbol}_bot.log')

    with open(log_file, 'a') as lf:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT,
            stdout=lf, stderr=subprocess.STDOUT,
        )
    _running_bots[symbol] = proc
    logger.info("Started bot for %s: PID=%d, cmd=%s", symbol, proc.pid, ' '.join(cmd))
    return True


def _stop_bot(symbol: str) -> bool:
    """Stop a running bot process."""
    proc = _running_bots.get(symbol)
    if proc is None or proc.poll() is not None:
        _running_bots.pop(symbol, None)
        return False
    try:
        proc.terminate()
        proc.wait(timeout=10)
        logger.info("Stopped bot for %s (PID=%d)", symbol, proc.pid)
    except subprocess.TimeoutExpired:
        proc.kill()
        logger.warning("Force-killed bot for %s (PID=%d)", symbol, proc.pid)
    _running_bots.pop(symbol, None)
    return True


def _stop_all_bots():
    """Stop all running bot processes."""
    for symbol in list(_running_bots.keys()):
        _stop_bot(symbol)


def _compute_summary(state: dict) -> dict:
    """Derive KPI metrics from raw state."""
    if not state:
        return {}

    open_groups = state.get('open_groups', {})
    closed_groups = state.get('closed_groups', [])
    total_pnl = state.get('total_pnl', 0.0)
    total_cycles = state.get('total_cycles', 0)

    bot_a_entry = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'ENTRY_PENDING')
    bot_a_target = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'TARGET_PENDING')
    bot_b_entry = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'ENTRY_PENDING')
    bot_b_target = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'TARGET_PENDING')

    wins = sum(1 for g in closed_groups if g.get('realized_pnl', 0) > 0)
    win_rate = (wins / len(closed_groups) * 100) if closed_groups else 0.0

    filled_groups = [g for g in open_groups.values() if g.get('status') == 'TARGET_PENDING']
    long_exposure = sum(g.get('qty', 0) for g in filled_groups if g.get('entry_side') == 'BUY')
    short_exposure = sum(g.get('qty', 0) for g in filled_groups if g.get('entry_side') == 'SELL')

    pair_pnl = round(sum(g.get('pair_pnl', 0.0) for g in closed_groups), 2)
    # Include pair PnL from open groups (partial hedges already realized)
    open_pair_pnl = round(sum(g.get('pair_pnl', 0.0) for g in open_groups.values()), 2)
    pair_pnl += open_pair_pnl
    combined_pnl = round(total_pnl + pair_pnl, 2)

    return {
        'symbol': state.get('symbol', ''),
        'anchor_price': state.get('anchor_price', 0),
        'total_pnl': round(total_pnl, 2),
        'pair_pnl': pair_pnl,
        'combined_pnl': combined_pnl,
        'total_cycles': total_cycles,
        'open_groups': len(open_groups),
        'win_rate': round(win_rate, 1),
        'bot_a': {'entry_pending': bot_a_entry, 'target_pending': bot_a_target},
        'bot_b': {'entry_pending': bot_b_entry, 'target_pending': bot_b_target},
        'long_exposure': long_exposure,
        'short_exposure': short_exposure,
        'last_updated': state.get('last_updated', ''),
    }


def create_app() -> Flask:
    """Create Flask app for config + monitor dashboard."""
    app = Flask(__name__)

    @app.route('/api/config', methods=['GET'])
    def api_get_config():
        return jsonify(_load_config())

    @app.route('/api/config', methods=['POST'])
    def api_save_config():
        try:
            new_config = request.get_json()
            if not new_config:
                return jsonify({'error': 'No JSON body'}), 400
            _save_config(new_config)
            return jsonify({'status': 'ok'})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/bot/start/<symbol>', methods=['POST'])
    def api_start_bot(symbol):
        config = _load_config()
        if _start_bot(symbol, config):
            return jsonify({'status': 'started', 'symbol': symbol})
        return jsonify({'error': f'Failed to start {symbol}'}), 400

    @app.route('/api/bot/stop/<symbol>', methods=['POST'])
    def api_stop_bot(symbol):
        if _stop_bot(symbol):
            return jsonify({'status': 'stopped', 'symbol': symbol})
        return jsonify({'error': f'{symbol} not running'}), 400

    @app.route('/api/bot/stop-all', methods=['POST'])
    def api_stop_all():
        _stop_all_bots()
        return jsonify({'status': 'all stopped'})

    @app.route('/api/state')
    def api_state_all():
        config = _load_config()
        result = {}
        for p in config.get('primaries', []):
            sym = p['symbol']
            state = _load_state(sym)
            result[sym] = {
                'state': state,
                'summary': _compute_summary(state),
                'running': _is_bot_running(sym),
                'pid': _running_bots[sym].pid if sym in _running_bots and _running_bots[sym].poll() is None else None,
            }
        return jsonify(result)

    @app.route('/api/state/<symbol>')
    def api_state_symbol(symbol):
        state = _load_state(symbol)
        return jsonify({
            'state': state,
            'summary': _compute_summary(state),
            'running': _is_bot_running(symbol),
        })

    @app.route('/api/processes')
    def api_processes():
        result = {}
        for sym, proc in list(_running_bots.items()):
            running = proc.poll() is None
            result[sym] = {
                'pid': proc.pid,
                'running': running,
                'returncode': proc.returncode if not running else None,
            }
        return jsonify(result)

    @app.route('/')
    def index():
        return Response(_build_html(), mimetype='text/html')

    return app


def _build_html() -> str:
    """Build the complete self-contained HTML dashboard."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Grid Bot Control Panel</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    :root {
        --bg: #0f1117;
        --card: #1a1d27;
        --border: #2a2d3a;
        --text: #e0e0e0;
        --dim: #888;
        --green: #00c853;
        --red: #ff1744;
        --blue: #448aff;
        --orange: #ff9100;
        --purple: #b388ff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
        background: var(--bg);
        color: var(--text);
        font-size: 13px;
    }
    .pulse {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 2s ease-in-out infinite;
    }
    .pulse-green { background: var(--green); }
    .pulse-red { background: var(--red); }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    .pnl-pos { color: var(--green); font-weight: 600; }
    .pnl-neg { color: var(--red); font-weight: 600; }
    .status-badge {
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
    }
    .badge-running { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-stopped { background: rgba(255,23,68,0.15); color: var(--red); }
    .badge-entry { background: rgba(255,145,0,0.15); color: var(--orange); }
    .badge-target { background: rgba(68,138,255,0.15); color: var(--blue); }
    .badge-closed { background: rgba(0,200,83,0.15); color: var(--green); }
    input, select {
        background: #0f1117;
        border: 1px solid var(--border);
        color: var(--text);
        padding: 4px 8px;
        border-radius: 4px;
        font-family: inherit;
        font-size: 12px;
    }
    input:focus, select:focus { outline: 1px solid var(--blue); }
    button {
        font-family: inherit;
        font-size: 12px;
        cursor: pointer;
        border: none;
        border-radius: 4px;
        padding: 6px 12px;
        font-weight: 600;
        transition: opacity 0.15s;
    }
    button:hover { opacity: 0.85; }
    .btn-green { background: var(--green); color: #000; }
    .btn-red { background: var(--red); color: #fff; }
    .btn-blue { background: var(--blue); color: #fff; }
    .btn-dim { background: var(--border); color: var(--text); }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }
    th {
        text-align: left;
        padding: 6px 8px;
        border-bottom: 1px solid var(--border);
        color: var(--dim);
        font-weight: 500;
        font-size: 11px;
        text-transform: uppercase;
    }
    td {
        padding: 5px 8px;
        border-bottom: 1px solid #1e2130;
    }
    tr:hover td { background: rgba(68,138,255,0.05); }
    .tab-active {
        border-bottom: 2px solid var(--blue);
        color: var(--blue);
    }
</style>
</head>
<body class="p-4">

<!-- HEADER -->
<div class="flex justify-between items-center p-3 rounded-lg mb-4" style="background:var(--card);border:1px solid var(--border);">
    <div>
        <h1 class="text-lg font-bold">TG GRID BOT CONTROL PANEL</h1>
        <span style="color:var(--dim);font-size:12px;" id="hdr-secondary">Secondary: —</span>
    </div>
    <div class="text-right" style="font-size:12px;">
        <span class="pulse pulse-green" id="status-pulse"></span>
        <span id="status-text">Loading...</span><br>
        <span style="color:var(--dim);" id="hdr-time">—</span>
    </div>
</div>

<!-- TABS -->
<div class="flex gap-4 mb-4 border-b" style="border-color:var(--border);">
    <button class="pb-2 px-1 bg-transparent tab-active" style="color:var(--blue);" onclick="switchTab('config')" id="tab-config">Configuration</button>
    <button class="pb-2 px-1 bg-transparent" style="color:var(--dim);" onclick="switchTab('monitor')" id="tab-monitor">Live Monitor</button>
    <button class="pb-2 px-1 bg-transparent" style="color:var(--dim);" onclick="switchTab('trades')" id="tab-trades">Trades</button>
</div>

<!-- CONFIG TAB -->
<div id="panel-config">
    <!-- Global Config -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Global Settings</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Secondary Symbol</label>
                <input id="cfg-secondary" value="SPCENET" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Zerodha User</label>
                <input id="cfg-zerodha-user" value="Sai" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">XTS Key</label>
                <input id="cfg-xts-key" class="w-full" style="font-size:10px;">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">XTS Root</label>
                <input id="cfg-xts-root" class="w-full" style="font-size:10px;">
            </div>
        </div>
    </div>

    <!-- Primary Configs -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <div class="flex justify-between items-center mb-3">
            <h2 class="text-sm font-semibold" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Primary Configs</h2>
            <button class="btn-blue text-xs" onclick="addPrimary()">+ Add Primary</button>
        </div>
        <div id="primaries-container"></div>
    </div>

    <div class="flex gap-2 mb-4">
        <button class="btn-green" onclick="saveConfig()">Save Config</button>
        <button class="btn-dim" onclick="loadConfig()">Reload</button>
    </div>
</div>

<!-- MONITOR TAB -->
<div id="panel-monitor" style="display:none;">
    <!-- Aggregate KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4" id="agg-kpis">
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Combined PnL</div>
            <div class="text-xl font-bold" id="agg-combined-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Primary PnL</div>
            <div class="text-xl font-bold" id="agg-primary-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Secondary PnL</div>
            <div class="text-xl font-bold" id="agg-pair-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Total Cycles</div>
            <div class="text-xl font-bold" style="color:var(--blue);" id="agg-cycles">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Open Groups</div>
            <div class="text-xl font-bold" style="color:var(--orange);" id="agg-open">—</div>
        </div>
    </div>

    <!-- Per-primary PnL breakdown table -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Per-Primary PnL Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Primary</th>
                    <th>Status</th>
                    <th>Anchor</th>
                    <th>1&deg; PnL</th>
                    <th>2&deg; PnL</th>
                    <th>Combined</th>
                    <th>Cycles</th>
                    <th>Open</th>
                    <th>Win Rate</th>
                </tr>
            </thead>
            <tbody id="breakdown-tbody"></tbody>
        </table>
    </div>

    <!-- Open Positions -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Open Positions</h2>
        <table>
            <thead>
                <tr>
                    <th>Primary</th>
                    <th>Group</th>
                    <th>Bot</th>
                    <th>Level</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Target</th>
                    <th>Qty</th>
                    <th>Hedged</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody id="open-tbody"></tbody>
        </table>
        <div class="text-center py-4" style="color:var(--dim);font-style:italic;display:none;" id="open-empty">No open positions</div>
    </div>

    <!-- PnL Chart -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Cumulative PnL</h2>
        <div style="height:200px;position:relative;">
            <canvas id="pnl-chart"></canvas>
        </div>
    </div>
</div>

<!-- TRADES TAB -->
<div id="panel-trades" style="display:none;">
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Recent Transactions (Last 50)</h2>
        <table>
            <thead>
                <tr>
                    <th>Primary</th>
                    <th>Group</th>
                    <th>Bot</th>
                    <th>Level</th>
                    <th>Buy @</th>
                    <th>Sell @</th>
                    <th>Qty</th>
                    <th>1&deg; PnL</th>
                    <th>2&deg; PnL</th>
                    <th>Combined</th>
                    <th>Closed</th>
                </tr>
            </thead>
            <tbody id="closed-tbody"></tbody>
        </table>
        <div class="text-center py-4" style="color:var(--dim);font-style:italic;display:none;" id="closed-empty">No completed trades yet</div>
    </div>
</div>

<!-- EDIT MODAL -->
<div id="edit-modal" class="fixed inset-0 flex items-center justify-center" style="background:rgba(0,0,0,0.6);display:none;z-index:50;">
    <div class="rounded-lg p-6 w-full max-w-lg" style="background:var(--card);border:1px solid var(--border);">
        <h3 class="text-base font-semibold mb-4" id="modal-title">Edit Primary</h3>
        <div class="grid grid-cols-2 gap-3">
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Symbol</label>
                <input id="m-symbol" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Product</label>
                <select id="m-product" class="w-full">
                    <option value="NRML">NRML</option>
                    <option value="MIS">MIS</option>
                </select>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Grid Space</label>
                <input id="m-grid-space" type="number" step="0.01" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Target</label>
                <input id="m-target" type="number" step="0.01" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Total Qty</label>
                <input id="m-total-qty" type="number" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Subset Qty</label>
                <input id="m-subset-qty" type="number" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Hedge Ratio</label>
                <input id="m-hedge-ratio" type="number" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Partial Hedge Ratio</label>
                <input id="m-partial-hedge-ratio" type="number" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Holdings Override</label>
                <input id="m-holdings" type="number" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Poll Interval (s)</label>
                <input id="m-poll" type="number" step="0.5" class="w-full">
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Anchor Price (0=auto)</label>
                <input id="m-anchor" type="number" step="0.01" class="w-full">
            </div>
            <div class="flex items-end">
                <label class="flex items-center gap-2 text-xs" style="color:var(--dim);">
                    <input type="checkbox" id="m-auto-anchor"> Auto Anchor (LTP)
                </label>
            </div>
        </div>
        <div class="flex gap-2 mt-4 justify-end">
            <button class="btn-dim" onclick="closeModal()">Cancel</button>
            <button class="btn-green" onclick="saveModal()">Save</button>
        </div>
    </div>
</div>

<script>
let currentConfig = {};
let editingIdx = -1;
let pnlChart = null;

// --- Tab switching ---
function switchTab(tab) {
    ['config','monitor','trades'].forEach(t => {
        document.getElementById('panel-' + t).style.display = (t === tab) ? 'block' : 'none';
        const btn = document.getElementById('tab-' + t);
        if (t === tab) {
            btn.classList.add('tab-active');
            btn.style.color = 'var(--blue)';
        } else {
            btn.classList.remove('tab-active');
            btn.style.color = 'var(--dim)';
        }
    });
}

// --- Config management ---
function loadConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            currentConfig = cfg;
            document.getElementById('cfg-secondary').value = cfg.secondary_symbol || '';
            document.getElementById('cfg-zerodha-user').value = cfg.zerodha_user || 'Sai';
            document.getElementById('cfg-xts-key').value = cfg.xts_interactive_key || '';
            document.getElementById('cfg-xts-root').value = cfg.xts_root || '';
            document.getElementById('hdr-secondary').textContent = 'Secondary: ' + (cfg.secondary_symbol || 'None');
            renderPrimaries();
        })
        .catch(e => console.error('Load config error:', e));
}

function saveConfig() {
    currentConfig.secondary_symbol = document.getElementById('cfg-secondary').value;
    currentConfig.zerodha_user = document.getElementById('cfg-zerodha-user').value;
    currentConfig.xts_interactive_key = document.getElementById('cfg-xts-key').value;
    currentConfig.xts_root = document.getElementById('cfg-xts-root').value;
    fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(currentConfig),
    })
    .then(r => r.json())
    .then(r => {
        if (r.status === 'ok') {
            document.getElementById('hdr-secondary').textContent = 'Secondary: ' + currentConfig.secondary_symbol;
        }
    })
    .catch(e => console.error('Save config error:', e));
}

function renderPrimaries() {
    const container = document.getElementById('primaries-container');
    const primaries = currentConfig.primaries || [];
    if (primaries.length === 0) {
        container.innerHTML = '<div style="color:var(--dim);text-align:center;padding:20px;">No primaries configured. Click "+ Add Primary" to get started.</div>';
        return;
    }
    container.innerHTML = primaries.map((p, i) => {
        const sym = p.symbol || 'UNNAMED';
        const running = botStatuses[sym] || false;
        const statusBadge = running
            ? '<span class="status-badge badge-running">Running</span>'
            : '<span class="status-badge badge-stopped">Stopped</span>';
        const startStopBtn = running
            ? `<button class="btn-red text-xs" onclick="stopBot('${sym}')">Stop</button>`
            : `<button class="btn-green text-xs" onclick="startBot('${sym}')">Start</button>`;
        return `
        <div class="rounded p-3 mb-2 flex justify-between items-center" style="background:#0f1117;border:1px solid var(--border);">
            <div>
                <span class="font-bold text-sm">${sym}</span> ${statusBadge}
                <div class="text-xs mt-1" style="color:var(--dim);">
                    Qty:${p.total_qty} Space:${p.grid_space} Target:${p.target}
                    Hedge:${p.hedge_ratio} Partial:${p.partial_hedge_ratio}
                    Holdings:${p.holdings_override} Product:${p.product}
                </div>
            </div>
            <div class="flex gap-1">
                ${startStopBtn}
                <button class="btn-blue text-xs" onclick="editPrimary(${i})">Edit</button>
                <button class="btn-dim text-xs" onclick="removePrimary(${i})">Remove</button>
            </div>
        </div>`;
    }).join('');
}

function addPrimary() {
    if (!currentConfig.primaries) currentConfig.primaries = [];
    currentConfig.primaries.push({
        symbol: '',
        enabled: true,
        auto_anchor: true,
        anchor_price: 0,
        grid_space: 0.01,
        target: 0.03,
        total_qty: 10,
        subset_qty: 1,
        hedge_ratio: 1,
        partial_hedge_ratio: 1,
        holdings_override: 1000,
        product: 'NRML',
        poll_interval: 2.0,
    });
    editPrimary(currentConfig.primaries.length - 1);
}

function removePrimary(idx) {
    const sym = currentConfig.primaries[idx].symbol;
    if (confirm('Remove ' + sym + '?')) {
        currentConfig.primaries.splice(idx, 1);
        renderPrimaries();
    }
}

function editPrimary(idx) {
    editingIdx = idx;
    const p = currentConfig.primaries[idx];
    document.getElementById('modal-title').textContent = p.symbol ? 'Edit ' + p.symbol : 'New Primary';
    document.getElementById('m-symbol').value = p.symbol || '';
    document.getElementById('m-product').value = p.product || 'NRML';
    document.getElementById('m-grid-space').value = p.grid_space || 0.01;
    document.getElementById('m-target').value = p.target || 0.03;
    document.getElementById('m-total-qty').value = p.total_qty || 10;
    document.getElementById('m-subset-qty').value = p.subset_qty || 1;
    document.getElementById('m-hedge-ratio').value = p.hedge_ratio || 0;
    document.getElementById('m-partial-hedge-ratio').value = p.partial_hedge_ratio || 0;
    document.getElementById('m-holdings').value = p.holdings_override != null ? p.holdings_override : -1;
    document.getElementById('m-poll').value = p.poll_interval || 2.0;
    document.getElementById('m-anchor').value = p.anchor_price || 0;
    document.getElementById('m-auto-anchor').checked = p.auto_anchor !== false;
    document.getElementById('edit-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('edit-modal').style.display = 'none';
    editingIdx = -1;
}

function saveModal() {
    if (editingIdx < 0) return;
    const p = currentConfig.primaries[editingIdx];
    p.symbol = document.getElementById('m-symbol').value.toUpperCase().trim();
    p.product = document.getElementById('m-product').value;
    p.grid_space = parseFloat(document.getElementById('m-grid-space').value);
    p.target = parseFloat(document.getElementById('m-target').value);
    p.total_qty = parseInt(document.getElementById('m-total-qty').value);
    p.subset_qty = parseInt(document.getElementById('m-subset-qty').value);
    p.hedge_ratio = parseInt(document.getElementById('m-hedge-ratio').value);
    p.partial_hedge_ratio = parseInt(document.getElementById('m-partial-hedge-ratio').value);
    p.holdings_override = parseInt(document.getElementById('m-holdings').value);
    p.poll_interval = parseFloat(document.getElementById('m-poll').value);
    p.anchor_price = parseFloat(document.getElementById('m-anchor').value);
    p.auto_anchor = document.getElementById('m-auto-anchor').checked;
    closeModal();
    renderPrimaries();
}

// --- Bot control ---
let botStatuses = {};

function startBot(symbol) {
    fetch('/api/bot/start/' + symbol, {method: 'POST'})
        .then(r => r.json())
        .then(r => { updateProcesses(); })
        .catch(e => console.error('Start error:', e));
}

function stopBot(symbol) {
    fetch('/api/bot/stop/' + symbol, {method: 'POST'})
        .then(r => r.json())
        .then(r => { updateProcesses(); })
        .catch(e => console.error('Stop error:', e));
}

function updateProcesses() {
    fetch('/api/processes')
        .then(r => r.json())
        .then(procs => {
            botStatuses = {};
            for (const [sym, info] of Object.entries(procs)) {
                botStatuses[sym] = info.running;
            }
            renderPrimaries();
            updateStatusIndicator();
        })
        .catch(e => {});
}

function updateStatusIndicator() {
    const running = Object.values(botStatuses).some(v => v);
    const pulse = document.getElementById('status-pulse');
    const text = document.getElementById('status-text');
    if (running) {
        pulse.className = 'pulse pulse-green';
        const count = Object.values(botStatuses).filter(v => v).length;
        text.textContent = count + ' bot' + (count > 1 ? 's' : '') + ' running';
    } else {
        pulse.className = 'pulse pulse-red';
        text.textContent = 'All stopped';
    }
    document.getElementById('hdr-time').textContent = new Date().toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}

// --- Monitor update ---
function fmtPnl(v) {
    if (v == null || isNaN(v)) return '<span style="color:var(--dim);">—</span>';
    const cls = v >= 0 ? 'pnl-pos' : 'pnl-neg';
    return '<span class="' + cls + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '</span>';
}

function fmtPnlText(v) {
    if (v == null || isNaN(v)) return '—';
    return (v >= 0 ? '+' : '') + v.toFixed(2);
}

function fmtTime(iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return d.toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
    } catch(e) { return iso; }
}

function updateMonitor() {
    fetch('/api/state')
        .then(r => r.json())
        .then(allStates => {
            let aggPrimary = 0, aggPair = 0, aggCycles = 0, aggOpen = 0;
            const breakdownRows = [];
            const openRows = [];
            let allClosed = [];

            for (const [sym, data] of Object.entries(allStates)) {
                const s = data.summary || {};
                const state = data.state || {};
                const running = data.running;

                botStatuses[sym] = running;

                const primaryPnl = s.total_pnl || 0;
                const pairPnl = s.pair_pnl || 0;
                const combined = s.combined_pnl || 0;
                const cycles = s.total_cycles || 0;
                const open = s.open_groups || 0;
                const winRate = s.win_rate || 0;

                aggPrimary += primaryPnl;
                aggPair += pairPnl;
                aggCycles += cycles;
                aggOpen += open;

                const statusBadge = running
                    ? '<span class="status-badge badge-running">Running</span>'
                    : '<span class="status-badge badge-stopped">Stopped</span>';

                breakdownRows.push('<tr>' +
                    '<td class="font-bold">' + sym + '</td>' +
                    '<td>' + statusBadge + '</td>' +
                    '<td>' + (s.anchor_price || 0).toFixed(2) + '</td>' +
                    '<td>' + fmtPnl(primaryPnl) + '</td>' +
                    '<td>' + fmtPnl(pairPnl) + '</td>' +
                    '<td>' + fmtPnl(combined) + '</td>' +
                    '<td>' + cycles + '</td>' +
                    '<td>' + open + '</td>' +
                    '<td>' + winRate.toFixed(1) + '%</td>' +
                    '</tr>');

                // Open positions
                const og = state.open_groups || {};
                Object.values(og).sort((a,b) => a.subset_index - b.subset_index).forEach(g => {
                    const statusCls = g.status === 'ENTRY_PENDING' ? 'badge-entry' : 'badge-target';
                    openRows.push('<tr>' +
                        '<td class="font-bold">' + sym + '</td>' +
                        '<td>' + g.group_id + '</td>' +
                        '<td>' + (g.bot === 'A' ? 'A (Buy)' : 'B (Sell)') + '</td>' +
                        '<td>L' + g.subset_index + '</td>' +
                        '<td>' + g.entry_side + '</td>' +
                        '<td>' + (g.entry_fill_price || g.entry_price).toFixed(2) + '</td>' +
                        '<td>' + g.target_price.toFixed(2) + '</td>' +
                        '<td>' + g.qty + '</td>' +
                        '<td>' + (g.pair_hedged_qty || 0) + '</td>' +
                        '<td><span class="status-badge ' + statusCls + '">' + g.status.replace('_',' ') + '</span></td>' +
                        '</tr>');
                });

                // Closed trades
                (state.closed_groups || []).forEach(g => {
                    g._primary = sym;
                    allClosed.push(g);
                });
            }

            // Aggregate KPIs
            const aggCombined = aggPrimary + aggPair;
            const combEl = document.getElementById('agg-combined-pnl');
            combEl.textContent = fmtPnlText(aggCombined);
            combEl.className = 'text-xl font-bold ' + (aggCombined >= 0 ? 'pnl-pos' : 'pnl-neg');

            const primEl = document.getElementById('agg-primary-pnl');
            primEl.textContent = fmtPnlText(aggPrimary);
            primEl.className = 'text-xl font-bold ' + (aggPrimary >= 0 ? 'pnl-pos' : 'pnl-neg');

            const pairEl = document.getElementById('agg-pair-pnl');
            pairEl.textContent = fmtPnlText(aggPair);
            pairEl.className = 'text-xl font-bold ' + (aggPair >= 0 ? 'pnl-pos' : 'pnl-neg');

            document.getElementById('agg-cycles').textContent = aggCycles;
            document.getElementById('agg-open').textContent = aggOpen;

            // Totals row
            breakdownRows.push('<tr style="border-top:2px solid var(--border);font-weight:bold;">' +
                '<td>TOTAL</td><td></td><td></td>' +
                '<td>' + fmtPnl(aggPrimary) + '</td>' +
                '<td>' + fmtPnl(aggPair) + '</td>' +
                '<td>' + fmtPnl(aggCombined) + '</td>' +
                '<td>' + aggCycles + '</td>' +
                '<td>' + aggOpen + '</td>' +
                '<td></td></tr>');

            document.getElementById('breakdown-tbody').innerHTML = breakdownRows.join('');

            // Open positions
            const openTbody = document.getElementById('open-tbody');
            const openEmpty = document.getElementById('open-empty');
            if (openRows.length === 0) {
                openTbody.innerHTML = '';
                openEmpty.style.display = 'block';
            } else {
                openEmpty.style.display = 'none';
                openTbody.innerHTML = openRows.join('');
            }

            // Closed trades (last 50, sorted by close time)
            allClosed.sort((a,b) => (b.closed_at || '').localeCompare(a.closed_at || ''));
            allClosed = allClosed.slice(0, 50);
            const closedTbody = document.getElementById('closed-tbody');
            const closedEmpty = document.getElementById('closed-empty');
            if (allClosed.length === 0) {
                closedTbody.innerHTML = '';
                closedEmpty.style.display = 'block';
            } else {
                closedEmpty.style.display = 'none';
                closedTbody.innerHTML = allClosed.map(g => {
                    const buyP = g.entry_side === 'BUY' ? (g.entry_fill_price || g.entry_price) : (g.target_fill_price || g.target_price);
                    const sellP = g.entry_side === 'SELL' ? (g.entry_fill_price || g.entry_price) : (g.target_fill_price || g.target_price);
                    const combined = (g.realized_pnl || 0) + (g.pair_pnl || 0);
                    return '<tr>' +
                        '<td class="font-bold">' + (g._primary || '') + '</td>' +
                        '<td>' + g.group_id + '</td>' +
                        '<td>' + (g.bot === 'A' ? 'A' : 'B') + '</td>' +
                        '<td>L' + g.subset_index + '</td>' +
                        '<td>' + buyP.toFixed(2) + '</td>' +
                        '<td>' + sellP.toFixed(2) + '</td>' +
                        '<td>' + g.qty + '</td>' +
                        '<td>' + fmtPnl(g.realized_pnl) + '</td>' +
                        '<td>' + fmtPnl(g.pair_pnl) + '</td>' +
                        '<td>' + fmtPnl(combined) + '</td>' +
                        '<td>' + fmtTime(g.closed_at) + '</td>' +
                        '</tr>';
                }).join('');
            }

            // PnL chart
            if (allClosed.length > 0) {
                // Reverse so earliest first
                const chronological = [...allClosed].reverse();
                let cumPrimary = 0, cumCombined = 0;
                const labels = [];
                const primaryData = [];
                const combinedData = [];
                chronological.forEach((g, i) => {
                    cumPrimary += g.realized_pnl || 0;
                    cumCombined += (g.realized_pnl || 0) + (g.pair_pnl || 0);
                    labels.push(i + 1);
                    primaryData.push(parseFloat(cumPrimary.toFixed(2)));
                    combinedData.push(parseFloat(cumCombined.toFixed(2)));
                });
                const ctx = document.getElementById('pnl-chart').getContext('2d');
                if (pnlChart) pnlChart.destroy();
                pnlChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Primary PnL',
                            data: primaryData,
                            borderColor: '#448aff',
                            fill: false,
                            tension: 0.3,
                            pointRadius: 0,
                            borderWidth: 2,
                        }, {
                            label: 'Combined PnL',
                            data: combinedData,
                            borderColor: combinedData[combinedData.length-1] >= 0 ? '#00c853' : '#ff1744',
                            backgroundColor: (combinedData[combinedData.length-1] >= 0 ? 'rgba(0,200,83,' : 'rgba(255,23,68,') + '0.1)',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 0,
                            borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: true, labels: { color: '#aaa' } },
                        },
                        scales: {
                            x: {
                                display: true,
                                title: { display: true, text: 'Trade #', color: '#888' },
                                ticks: { color: '#888', maxTicksLimit: 15 },
                                grid: { color: 'rgba(42,45,58,0.5)' },
                            },
                            y: {
                                display: true,
                                title: { display: true, text: 'PnL', color: '#888' },
                                ticks: { color: '#888' },
                                grid: { color: 'rgba(42,45,58,0.5)' },
                            }
                        }
                    }
                });
            }

            // Update process statuses
            renderPrimaries();
            updateStatusIndicator();
        })
        .catch(e => console.error('Monitor update error:', e));
}

// --- Init ---
loadConfig();
updateProcesses();
setInterval(updateMonitor, 3000);
setInterval(updateProcesses, 10000);
setTimeout(updateMonitor, 500);
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='TG Grid Bot Dashboard')
    parser.add_argument('--port', type=int, default=7777, help='Dashboard port (default: 7777)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    # Ensure config exists
    if not os.path.exists(CONFIG_FILE):
        _save_config(_DEFAULT_CONFIG)

    app = create_app()

    # Cleanup on exit
    import atexit
    atexit.register(_stop_all_bots)

    logger.info("Starting TG Dashboard on %s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
