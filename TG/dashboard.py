"""
TG Grid Bot Dashboard — Monitor (7777) + Config (7779) web UI.

Features:
- Monitor mode (--mode monitor, port 7777): Live PnL, open positions, trade history
- Config mode (--mode config, port 7779): Edit config, start/stop bots, manage primaries
- Shared backend: Config, state, and process management APIs

Usage:
    python -m TG.dashboard --port 7777 --mode monitor
    python -m TG.dashboard --port 7779 --mode config
"""

import argparse
import json
import os
import sys
import signal
import subprocess
import logging
import time
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
            "levels_per_side": 10,
            "qty_per_level": 100,
            "hedge_ratio": 1,
            "partial_hedge_ratio": 1,
            "holdings_override": 2000,
            "product": "NRML",
            "poll_interval": 2.0,
            "reanchor_epoch": 100,
            "max_grid_levels": 2000,
        }
    ],
}

# Shared PID file for cross-process bot state
_PID_FILE = os.path.join(STATE_DIR, '.bot_pids.json')


def _load_bot_pids() -> Dict[str, int]:
    """Load bot PIDs from shared file."""
    if not os.path.exists(_PID_FILE):
        return {}
    try:
        with open(_PID_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_bot_pids(pids: Dict[str, int]):
    """Save bot PIDs to shared file with atomic write."""
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = _PID_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(pids, f, indent=2)
    os.replace(tmp, _PID_FILE)


def _pid_alive(pid: int) -> bool:
    """Check if a PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


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
    """Check if a bot process is running for a symbol (via shared PID file)."""
    pids = _load_bot_pids()
    pid = pids.get(symbol)
    if pid is None:
        return False
    if _pid_alive(pid):
        return True
    # Stale PID — clean it up
    pids.pop(symbol, None)
    _save_bot_pids(pids)
    return False


def _get_bot_pid(symbol: str) -> Optional[int]:
    """Get the PID for a running bot, or None."""
    pids = _load_bot_pids()
    pid = pids.get(symbol)
    if pid and _pid_alive(pid):
        return pid
    return None


def _start_bot(symbol: str, config: dict) -> bool:
    """Launch TG.run as subprocess for a primary symbol."""
    if _is_bot_running(symbol):
        pid = _get_bot_pid(symbol)
        logger.warning("Bot for %s is already running (PID=%s)", symbol, pid)
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
        '--levels-per-side', str(primary.get('levels_per_side', 10)),
        '--qty-per-level', str(primary.get('qty_per_level', 100)),
        '--holdings', str(primary.get('holdings_override', -1)),
        '--product', primary.get('product', 'NRML'),
        '--interactive-key', config.get('xts_interactive_key', ''),
        '--interactive-secret', config.get('xts_interactive_secret', ''),
        '--user', config.get('zerodha_user', 'Sai'),
        '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
        '--poll-interval', str(primary.get('poll_interval', 2.0)),
        '--reanchor-epoch', str(primary.get('reanchor_epoch', 100)),
        '--max-grid-levels', str(primary.get('max_grid_levels', 2000)),
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

    # Record PID in shared file
    pids = _load_bot_pids()
    pids[symbol] = proc.pid
    _save_bot_pids(pids)

    logger.info("Started bot for %s: PID=%d, cmd=%s", symbol, proc.pid, ' '.join(cmd))
    return True


def _stop_bot(symbol: str) -> bool:
    """Stop a running bot process via shared PID file."""
    pids = _load_bot_pids()
    pid = pids.get(symbol)
    if pid is None:
        return False
    if not _pid_alive(pid):
        # Already dead, clean up
        pids.pop(symbol, None)
        _save_bot_pids(pids)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait up to 10s for process to exit
        for _ in range(20):
            time.sleep(0.5)
            if not _pid_alive(pid):
                break
        else:
            # Force kill if still alive
            os.kill(pid, signal.SIGKILL)
            logger.warning("Force-killed bot for %s (PID=%d)", symbol, pid)
        logger.info("Stopped bot for %s (PID=%d)", symbol, pid)
    except ProcessLookupError:
        pass
    except Exception as e:
        logger.error("Error stopping bot %s (PID=%d): %s", symbol, pid, e)

    pids.pop(symbol, None)
    _save_bot_pids(pids)
    return True


def _stop_all_bots():
    """Stop all running bot processes."""
    pids = _load_bot_pids()
    for symbol in list(pids.keys()):
        _stop_bot(symbol)


def _compute_summary(state: dict) -> dict:
    """Derive KPI metrics from raw state."""
    if not state:
        return {}

    from datetime import date
    today_str = date.today().isoformat()  # e.g. '2026-02-19'

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

    # Today-only metrics: filter closed_groups by closed_at date + open group pair PnL
    today_closed = [g for g in closed_groups if (g.get('closed_at') or '').startswith(today_str)]
    today_primary_pnl = round(sum(g.get('realized_pnl', 0.0) for g in today_closed), 2)
    today_pair_pnl = round(sum(g.get('pair_pnl', 0.0) for g in today_closed) + open_pair_pnl, 2)
    today_combined_pnl = round(today_primary_pnl + today_pair_pnl, 2)
    today_cycles = len(today_closed)
    today_wins = sum(1 for g in today_closed if g.get('realized_pnl', 0) > 0)
    today_win_rate = (today_wins / today_cycles * 100) if today_cycles else 0.0

    return {
        'symbol': state.get('symbol', ''),
        'anchor_price': state.get('anchor_price', 0),
        'main_anchor': state.get('main_anchor', 0),
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
        'buy_grid_levels': state.get('buy_grid_levels', 0),
        'sell_grid_levels': state.get('sell_grid_levels', 0),
        'current_buy_spacing': state.get('current_buy_spacing', 0),
        'current_sell_spacing': state.get('current_sell_spacing', 0),
        'last_updated': state.get('last_updated', ''),
        # Today-only metrics
        'today_primary_pnl': today_primary_pnl,
        'today_pair_pnl': today_pair_pnl,
        'today_combined_pnl': today_combined_pnl,
        'today_cycles': today_cycles,
        'today_win_rate': round(today_win_rate, 1),
    }


def create_app(mode: str = 'monitor') -> Flask:
    """Create Flask app. mode='monitor' for 7777, mode='config' for 7779."""
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
                'pid': _get_bot_pid(sym),
                'config': {
                    'grid_space': p.get('grid_space', 0.01),
                    'target': p.get('target', 0.03),
                    'levels_per_side': p.get('levels_per_side', 10),
                    'qty_per_level': p.get('qty_per_level', 100),
                    'hedge_ratio': p.get('hedge_ratio', 0),
                    'partial_hedge_ratio': p.get('partial_hedge_ratio', 0),
                    'product': p.get('product', 'NRML'),
                    'reanchor_epoch': p.get('reanchor_epoch', 100),
                    'max_grid_levels': p.get('max_grid_levels', 2000),
                },
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
        pids = _load_bot_pids()
        result = {}
        stale = []
        for sym, pid in pids.items():
            alive = _pid_alive(pid)
            result[sym] = {
                'pid': pid,
                'running': alive,
            }
            if not alive:
                stale.append(sym)
        # Clean up stale PIDs
        if stale:
            for sym in stale:
                pids.pop(sym, None)
            _save_bot_pids(pids)
        return jsonify(result)

    @app.route('/')
    def index():
        if mode == 'config':
            return Response(_build_config_html(), mimetype='text/html')
        return Response(_build_html(), mimetype='text/html')

    return app


def _build_html() -> str:
    """Build the complete self-contained HTML monitor dashboard with per-bot tabs."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Grid Bot Monitor Panel</title>
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
        --cyan: #18ffff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
        background: var(--bg);
        color: var(--text);
        font-size: 13px;
    }
    .pulse {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 6px; animation: pulse 2s ease-in-out infinite;
    }
    .pulse-green { background: var(--green); }
    .pulse-red { background: var(--red); }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .pnl-pos { color: var(--green); font-weight: 600; }
    .pnl-neg { color: var(--red); font-weight: 600; }
    .status-badge {
        display: inline-block; padding: 2px 6px; border-radius: 4px;
        font-size: 10px; font-weight: 600;
    }
    .badge-running { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-stopped { background: rgba(255,23,68,0.15); color: var(--red); }
    .badge-entry { background: rgba(255,145,0,0.15); color: var(--orange); }
    .badge-target { background: rgba(68,138,255,0.15); color: var(--blue); }
    .badge-closed { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-buy { background: rgba(0,200,83,0.10); color: var(--green); }
    .badge-sell { background: rgba(255,23,68,0.10); color: var(--red); }
    button {
        font-family: inherit; font-size: 12px; cursor: pointer; border: none;
        border-radius: 4px; padding: 6px 12px; font-weight: 600;
        transition: opacity 0.15s;
    }
    button:hover { opacity: 0.85; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th {
        text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border);
        color: var(--dim); font-weight: 500; font-size: 11px; text-transform: uppercase;
    }
    td { padding: 5px 8px; border-bottom: 1px solid #1e2130; }
    tr:hover td { background: rgba(68,138,255,0.05); }
    .tab-btn {
        background: transparent; color: var(--dim); padding: 8px 12px;
        border-bottom: 2px solid transparent; border-radius: 0;
    }
    .tab-btn.active { border-bottom-color: var(--blue); color: var(--blue); }
    .grid-row-active { background: rgba(68,138,255,0.08); }
    .grid-row-filled { background: rgba(0,200,83,0.08); }
    .grid-main-row { cursor: pointer; }
    .grid-main-row:hover td { background: rgba(68,138,255,0.10); }
    .grid-sub-row td { padding: 2px 8px 2px 24px; font-size: 11px; color: var(--dim); border-bottom: 1px solid rgba(30,33,48,0.5); }
    .grid-sub-row.hidden { display: none; }
    .grid-sub-label { display: inline-block; width: 52px; font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: 0.3px; }
    .grid-sub-label.entry-label { color: var(--blue); }
    .grid-sub-label.target-label { color: var(--orange); }
    .grid-sub-label.hedge-label { color: var(--purple); }
    .grid-sub-label.unwind-label { color: var(--yellow, #fdd835); }
    .grid-expand-icon { display: inline-block; width: 14px; font-size: 10px; color: var(--dim); transition: transform 0.15s; }
    .grid-expand-icon.open { transform: rotate(90deg); }
    .grid-id-mono { font-family: monospace; font-size: 10px; color: var(--dim); opacity: 0.7; }
    .grid-pnl-pos { color: var(--green); }
    .grid-pnl-neg { color: var(--red); }
</style>
</head>
<body class="p-4">

<!-- HEADER -->
<div class="flex justify-between items-center p-3 rounded-lg mb-4" style="background:var(--card);border:1px solid var(--border);">
    <div>
        <h1 class="text-lg font-bold">TG GRID BOT MONITOR PANEL</h1>
        <span style="color:var(--dim);font-size:12px;" id="hdr-secondary">Secondary: —</span>
    </div>
    <div class="text-right" style="font-size:12px;">
        <span class="pulse pulse-green" id="status-pulse"></span>
        <span id="status-text">Loading...</span><br>
        <span style="color:var(--dim);" id="hdr-time">—</span>
    </div>
</div>

<!-- TABS (dynamically populated) -->
<div class="flex gap-1 mb-4 border-b overflow-x-auto" style="border-color:var(--border);" id="tab-bar">
    <button class="tab-btn active" onclick="switchTab('monitor')" id="tab-monitor">Live Monitor</button>
    <!-- Per-bot tabs inserted dynamically -->
</div>

<!-- LIVE MONITOR TAB (aggregate) -->
<div id="panel-monitor">
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Combined PnL (Today)</div>
            <div class="text-xl font-bold" id="agg-combined-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Primary PnL (Today)</div>
            <div class="text-xl font-bold" id="agg-primary-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Secondary PnL (Today)</div>
            <div class="text-xl font-bold" id="agg-pair-pnl">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Cycles (Today)</div>
            <div class="text-xl font-bold" style="color:var(--blue);" id="agg-cycles">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Open Groups</div>
            <div class="text-xl font-bold" style="color:var(--orange);" id="agg-open">—</div>
        </div>
    </div>

    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Per-Primary PnL Breakdown</h2>
        <table>
            <thead><tr>
                <th>Primary</th><th>Status</th><th>Anchor</th>
                <th>1&deg; PnL</th><th>2&deg; PnL</th><th>Combined</th>
                <th>Cycles</th><th>Open</th><th>Win Rate</th>
            </tr></thead>
            <tbody id="breakdown-tbody"></tbody>
        </table>
    </div>

    <!-- Round Trips (all primaries combined) -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <div class="flex justify-between items-center mb-3">
            <h2 class="text-sm font-semibold" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Round Trips</h2>
            <select id="rt-filter" onchange="renderRoundTrips()" style="background:#0f1117;border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;font-family:inherit;font-size:12px;width:auto;">
                <option value="ALL">All Primaries</option>
            </select>
        </div>
        <div style="overflow-x:auto;">
            <table>
                <thead><tr>
                    <th>Cycle ID</th><th>Primary</th><th>Bot</th><th>Level</th><th>Side</th>
                    <th>Entry @</th><th>Exit @</th><th>Qty</th>
                    <th>1&deg; PnL</th><th>2&deg; PnL</th><th>Combined</th><th>Time</th>
                </tr></thead>
                <tbody id="roundtrips-tbody"></tbody>
            </table>
        </div>
        <div class="text-center py-3" style="color:var(--dim);font-style:italic;display:none;" id="roundtrips-empty">No completed round trips yet</div>
    </div>

    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Cumulative PnL</h2>
        <div style="height:200px;position:relative;"><canvas id="pnl-chart"></canvas></div>
    </div>
</div>

<!-- Per-bot panels are created dynamically -->
<div id="bot-panels"></div>

<script>
let currentConfig = {};
let pnlChart = null;
let secondarySymbol = '';
const expandedGridRows = new Set();
let botStatuses = {};
let allStatesCache = {};
let activeTab = 'monitor';
let knownPrimaries = [];
let allCyclesCache = [];
let allSecOrdersCache = [];

// --- Helpers ---
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
    try { return new Date(iso).toLocaleTimeString('en-IN', {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}); }
    catch(e) { return iso; }
}
function fmtDateTime(iso) {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return d.toLocaleDateString('en-IN',{day:'2-digit',month:'short'}) + ' ' +
               d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
    } catch(e) { return iso; }
}

// --- Tab management ---
function buildTabs(primaries) {
    const bar = document.getElementById('tab-bar');
    // Remove old dynamic tabs
    bar.querySelectorAll('.tab-btn-dynamic').forEach(b => b.remove());
    // Remove old panels
    document.getElementById('bot-panels').innerHTML = '';

    primaries.forEach(sym => {
        // Tab button
        const btn = document.createElement('button');
        btn.className = 'tab-btn tab-btn-dynamic';
        btn.id = 'tab-' + sym;
        btn.textContent = sym;
        btn.onclick = () => switchTab(sym);
        bar.appendChild(btn);

        // Panel
        const panel = document.createElement('div');
        panel.id = 'panel-' + sym;
        panel.style.display = 'none';
        panel.innerHTML = buildBotPanelHTML(sym);
        document.getElementById('bot-panels').appendChild(panel);
    });

    // Add SPCENET (secondary) tab
    const secBtn = document.createElement('button');
    secBtn.className = 'tab-btn tab-btn-dynamic';
    secBtn.id = 'tab-SECONDARY';
    secBtn.textContent = secondarySymbol || 'SPCENET';
    secBtn.style.borderColor = 'var(--purple)';
    secBtn.onclick = () => switchTab('SECONDARY');
    bar.appendChild(secBtn);

    const secPanel = document.createElement('div');
    secPanel.id = 'panel-SECONDARY';
    secPanel.style.display = 'none';
    secPanel.innerHTML = buildSecondaryPanelHTML();
    document.getElementById('bot-panels').appendChild(secPanel);

    knownPrimaries = primaries;
}

function switchTab(tab) {
    activeTab = tab;
    // Hide all panels
    document.getElementById('panel-monitor').style.display = 'none';
    knownPrimaries.forEach(sym => {
        const p = document.getElementById('panel-' + sym);
        if (p) p.style.display = 'none';
    });
    const secP = document.getElementById('panel-SECONDARY');
    if (secP) secP.style.display = 'none';

    // Show selected
    const target = document.getElementById('panel-' + tab);
    if (target) target.style.display = 'block';

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.id === 'tab-' + tab);
    });

    // Refresh panel data
    if (tab === 'SECONDARY') {
        renderSecondaryPanel(allStatesCache);
    } else if (tab !== 'monitor' && allStatesCache[tab]) {
        renderBotPanel(tab, allStatesCache[tab]);
    }
}

function buildBotPanelHTML(sym) {
    return `
    <!-- KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Status</div>
            <div class="text-base font-bold" id="${sym}-status">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Anchor</div>
            <div class="text-base font-bold" style="color:var(--blue);" id="${sym}-anchor">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Combined PnL (Today)</div>
            <div class="text-base font-bold" id="${sym}-combined">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Cycles (Today)</div>
            <div class="text-base font-bold" style="color:var(--blue);" id="${sym}-cycles">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Open / Win Rate (Today)</div>
            <div class="text-base font-bold" id="${sym}-open-wr">—</div>
        </div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Buy Reanchors</div>
            <div class="text-base font-bold" style="color:var(--green);" id="${sym}-buy-levels">0</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Buy Spacing</div>
            <div class="text-base font-bold" style="color:var(--green);" id="${sym}-buy-spacing">—</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Sell Reanchors</div>
            <div class="text-base font-bold" style="color:var(--red);" id="${sym}-sell-levels">0</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Sell Spacing</div>
            <div class="text-base font-bold" style="color:var(--red);" id="${sym}-sell-spacing">—</div>
        </div>
    </div>

    <!-- Grid Levels -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Grid Levels</h2>
        <div class="mb-4">
            <h3 class="text-xs font-semibold mb-2" style="color:var(--green);">BUY GRID (Bot A) — entries below anchor</h3>
            <table style="width:100%;">
                <thead><tr><th></th><th>Level</th><th>Entry → Target</th><th>Qty</th><th>Status</th><th>Primary PnL</th><th>Pair PnL</th><th>Cycle ID</th></tr></thead>
                <tbody id="${sym}-buy-grid"></tbody>
            </table>
        </div>
        <div>
            <h3 class="text-xs font-semibold mb-2" style="color:var(--red);">SELL GRID (Bot B) — entries above anchor</h3>
            <table style="width:100%;">
                <thead><tr><th></th><th>Level</th><th>Entry → Target</th><th>Qty</th><th>Status</th><th>Primary PnL</th><th>Pair PnL</th><th>Cycle ID</th></tr></thead>
                <tbody id="${sym}-sell-grid"></tbody>
            </table>
        </div>
    </div>

    <!-- Open Positions -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Open Positions</h2>
        <table>
            <thead><tr>
                <th>Group</th><th>Bot</th><th>Level</th><th>Side</th>
                <th>Entry</th><th>Fill @</th><th>Target</th><th>Qty</th>
                <th>Hedged</th><th>Status</th>
            </tr></thead>
            <tbody id="${sym}-open-tbody"></tbody>
        </table>
        <div class="text-center py-3" style="color:var(--dim);font-style:italic;display:none;" id="${sym}-open-empty">No open positions</div>
    </div>

    <!-- Recent Transactions -->
    <div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Recent Transactions</h2>
        <table>
            <thead><tr>
                <th>Group</th><th>Bot</th><th>Level</th><th>Type</th>
                <th>Buy @</th><th>Sell @</th><th>Qty</th><th>PnL</th><th>Time</th>
            </tr></thead>
            <tbody id="${sym}-closed-tbody"></tbody>
        </table>
        <div class="text-center py-3" style="color:var(--dim);font-style:italic;display:none;" id="${sym}-closed-empty">No completed trades yet</div>
    </div>`;
}

// --- Compute grid levels client-side ---
function computeGridLevels(anchor, gridSpace, target, levelsPerSide, qtyPerLevel, buySpacing, sellSpacing) {
    if (!anchor || anchor <= 0) return { buy: [], sell: [] };
    const buyLevels = [], sellLevels = [];
    const bSpace = buySpacing || gridSpace;
    const sSpace = sellSpacing || gridSpace;
    for (let i = 0; i < levelsPerSide; i++) {
        const bDist = bSpace * (i + 1);
        const sDist = sSpace * (i + 1);
        buyLevels.push({
            index: i,
            entry: Math.round((anchor - bDist) * 100) / 100,
            target: Math.round((anchor - bDist + target) * 100) / 100,
            qty: qtyPerLevel,
        });
        sellLevels.push({
            index: i,
            entry: Math.round((anchor + sDist) * 100) / 100,
            target: Math.round((anchor + sDist - target) * 100) / 100,
            qty: qtyPerLevel,
        });
    }
    return { buy: buyLevels, sell: sellLevels };
}

// --- Render a single grid level as main row + collapsible sub-rows ---
function renderGridLevel(lv, g, secSym, gridId) {
    const rid = gridId + '-' + lv.index;
    const isOpen = expandedGridRows.has(rid);
    // Determine status
    let statusHTML = '<span style="color:var(--dim);">Free</span>';
    let rowClass = '';
    let priceDisplay = lv.entry.toFixed(2) + ' → ' + lv.target.toFixed(2);
    let primaryPnl = '', pairPnl = '', cycleId = '';
    let hasDetails = false;

    if (g) {
        hasDetails = true;
        cycleId = '<span class="grid-id-mono">' + g.group_id + '</span>';
        // Prices: use fill prices when available, fallback to grid level
        const eP = g.entry_fill_price ? g.entry_fill_price.toFixed(2) : lv.entry.toFixed(2);
        const tP = g.target_fill_price ? g.target_fill_price.toFixed(2) : lv.target.toFixed(2);
        priceDisplay = eP + ' → ' + tP;
        if (g.status === 'ENTRY_PENDING') {
            statusHTML = '<span class="status-badge badge-entry">ENTRY PENDING</span>';
            rowClass = 'grid-row-active';
        } else if (g.status === 'TARGET_PENDING') {
            statusHTML = '<span class="status-badge badge-target">FILLED → TARGET</span>';
            rowClass = 'grid-row-filled';
        }
        // PnL
        if (g.realized_pnl) {
            const cls = g.realized_pnl >= 0 ? 'grid-pnl-pos' : 'grid-pnl-neg';
            primaryPnl = '<span class="' + cls + '">' + g.realized_pnl.toFixed(2) + '</span>';
        }
        if (g.pair_pnl) {
            const cls = g.pair_pnl >= 0 ? 'grid-pnl-pos' : 'grid-pnl-neg';
            pairPnl = '<span class="' + cls + '">' + g.pair_pnl.toFixed(2) + '</span>';
        }
    }

    // Main row
    const iconCls = (hasDetails && isOpen) ? 'grid-expand-icon open' : 'grid-expand-icon';
    const expandIcon = hasDetails ? '<span class="' + iconCls + '" id="icon-' + rid + '">&#9654;</span>' : '';
    let html = '<tr class="grid-main-row ' + rowClass + '" ' +
        (hasDetails ? 'onclick="toggleGridSub(\\'' + rid + '\\')" style="cursor:pointer;"' : '') + '>' +
        '<td style="width:20px;">' + expandIcon + '</td>' +
        '<td>L' + lv.index + '</td>' +
        '<td>' + priceDisplay + '</td>' +
        '<td>' + lv.qty + '</td>' +
        '<td>' + statusHTML + '</td>' +
        '<td>' + primaryPnl + '</td>' +
        '<td>' + pairPnl + '</td>' +
        '<td>' + cycleId + '</td></tr>';

    // Sub-rows — use expandedGridRows set to preserve open/closed state
    const subVis = isOpen ? 'grid-sub-row sub-' : 'grid-sub-row hidden sub-';
    if (g) {
        const cs = ' colspan="7"';
        // Entry sub-row: show order price, then fill info
        const eSide = g.entry_side || 'BUY';
        const ePrice = g.entry_price ? g.entry_price.toFixed(2) : lv.entry.toFixed(2);
        const eQty = g.entry_filled_so_far || 0;
        const eOid = g.entry_order_id ? g.entry_order_id : '—';
        let eDetail = '';
        if (eQty >= g.qty) {
            eDetail = '✓ filled' + (g.entry_fill_price ? ' @ ' + g.entry_fill_price.toFixed(2) : '');
        } else if (eQty > 0) {
            eDetail = 'partial ' + eQty + '/' + g.qty + (g.entry_fill_price ? ' @ ' + g.entry_fill_price.toFixed(2) : '');
        } else {
            eDetail = 'pending';
        }
        html += '<tr class="' + subVis + rid + '">' +
            '<td></td><td' + cs + '>' +
            '<span class="grid-sub-label entry-label">Entry</span> ' +
            eSide + ' ' + g.qty + ' @ ' + ePrice + '  <span style="opacity:0.6;">(' + eDetail + ')</span>' +
            '  <span class="grid-id-mono">OID:' + eOid + '</span>' +
            '</td></tr>';

        // Target sub-row: show order price, then fill info
        const tSide = eSide === 'BUY' ? 'SELL' : 'BUY';
        const tPrice = g.target_price ? g.target_price.toFixed(2) : lv.target.toFixed(2);
        const tQty = g.target_filled_so_far || 0;
        const tOid = g.target_order_id ? g.target_order_id : '—';
        let tDetail = '';
        if (tQty >= g.qty) {
            tDetail = '✓ filled' + (g.target_fill_price ? ' @ ' + g.target_fill_price.toFixed(2) : '');
        } else if (tQty > 0) {
            tDetail = 'partial ' + tQty + '/' + g.qty + (g.target_fill_price ? ' @ ' + g.target_fill_price.toFixed(2) : '');
        } else {
            tDetail = 'pending';
        }
        html += '<tr class="' + subVis + rid + '">' +
            '<td></td><td' + cs + '>' +
            '<span class="grid-sub-label target-label">Target</span> ' +
            tSide + ' ' + g.qty + ' @ ' + tPrice + '  <span style="opacity:0.6;">(' + tDetail + ')</span>' +
            '  <span class="grid-id-mono">OID:' + tOid + '</span>' +
            '</td></tr>';

        // Hedge sub-row (only if hedged)
        if (g.pair_hedged_qty && g.pair_hedged_qty > 0) {
            const hSide = eSide === 'BUY' ? 'SELL' : 'BUY';
            const hVwap = g.pair_hedge_vwap ? g.pair_hedge_vwap.toFixed(2) : '—';
            html += '<tr class="' + subVis + rid + '">' +
                '<td></td><td' + cs + '>' +
                '<span class="grid-sub-label hedge-label">Hedge</span> ' +
                hSide + ' ' + secSym + ' ' + g.pair_hedged_qty + ' @ ' + hVwap +
                '  <span class="grid-id-mono">(' + (g.pair_orders ? g.pair_orders.length : 0) + ' orders)</span>' +
                '</td></tr>';
        }

        // Unwind sub-row (only if unwound)
        if (g.pair_unwound_qty && g.pair_unwound_qty > 0) {
            const uSide = eSide === 'BUY' ? 'BUY' : 'SELL';
            const uVwap = g.pair_unwind_vwap ? g.pair_unwind_vwap.toFixed(2) : '—';
            const ppnl = g.pair_pnl ? g.pair_pnl.toFixed(2) : '0.00';
            const ppCls = g.pair_pnl >= 0 ? 'grid-pnl-pos' : 'grid-pnl-neg';
            html += '<tr class="' + subVis + rid + '">' +
                '<td></td><td' + cs + '>' +
                '<span class="grid-sub-label unwind-label">Unwind</span> ' +
                uSide + ' ' + secSym + ' ' + g.pair_unwound_qty + ' @ ' + uVwap +
                '  | Pair PnL: <span class="' + ppCls + '">' + ppnl + '</span>' +
                '</td></tr>';
        }
    }
    return html;
}

function toggleGridSub(rid) {
    const rows = document.querySelectorAll('.sub-' + rid);
    const icon = document.getElementById('icon-' + rid);
    const wasOpen = expandedGridRows.has(rid);
    if (wasOpen) {
        expandedGridRows.delete(rid);
        rows.forEach(r => r.classList.add('hidden'));
        if (icon) icon.classList.remove('open');
    } else {
        expandedGridRows.add(rid);
        rows.forEach(r => r.classList.remove('hidden'));
        if (icon) icon.classList.add('open');
    }
}

// --- Secondary (SPCENET) panel ---
function buildSecondaryPanelHTML() {
    const sym = secondarySymbol || 'SPCENET';
    return `
    <!-- KPIs -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Symbol</div>
            <div class="text-base font-bold" style="color:var(--purple);">${sym}</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Total Pair Orders</div>
            <div class="text-base font-bold" id="sec-total-orders">0</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Net Qty</div>
            <div class="text-base font-bold" id="sec-net-qty">0</div>
        </div>
        <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
            <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Pair PnL (All)</div>
            <div class="text-base font-bold" id="sec-total-pnl">0.00</div>
        </div>
    </div>
    <!-- Orders table -->
    <div class="rounded-lg p-4" style="background:var(--card);border:1px solid var(--border);">
        <div class="flex justify-between items-center mb-3">
            <h2 class="text-sm font-semibold" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">
                ${sym} Pair Orders</h2>
            <select id="sec-filter" onchange="renderSecondaryOrders()" style="background:#0f1117;border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;font-family:inherit;font-size:12px;width:auto;">
                <option value="ALL">All Primaries</option>
            </select>
        </div>
        <div style="overflow-x:auto;">
            <table class="data-table" style="min-width:900px;">
                <thead><tr>
                    <th>Time</th>
                    <th>Primary</th>
                    <th>Bot</th>
                    <th>Level</th>
                    <th>Role</th>
                    <th>Side</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>XTS Order ID</th>
                    <th>Custom ID</th>
                    <th>Group</th>
                </tr></thead>
                <tbody id="sec-orders-tbody"></tbody>
            </table>
        </div>
        <div id="sec-orders-empty" class="text-center py-6" style="color:var(--dim);">No pair orders yet</div>
    </div>`;
}

function renderSecondaryPanel(allStates) {
    if (!allStates) return;
    const orders = [];
    let totalPairPnl = 0;

    for (const [sym, data] of Object.entries(allStates)) {
        const state = data.state || {};
        const allGroups = Object.values(state.open_groups || {}).concat(state.closed_groups || []);
        allGroups.forEach(g => {
            (g.pair_orders || []).forEach(po => {
                orders.push({
                    primary: sym, bot: g.bot, level: g.subset_index,
                    group_id: g.group_id, ...po
                });
            });
            totalPairPnl += (g.pair_pnl || 0);
        });
    }

    // Sort newest first
    orders.sort((a, b) => (b.ts || '').localeCompare(a.ts || ''));
    allSecOrdersCache = orders;

    // KPIs (always show totals across all primaries)
    document.getElementById('sec-total-orders').textContent = orders.length;
    const buyQty = orders.filter(o => o.side === 'BUY').reduce((s, o) => s + (o.qty || 0), 0);
    const sellQty = orders.filter(o => o.side === 'SELL').reduce((s, o) => s + (o.qty || 0), 0);
    const netQty = buyQty - sellQty;
    const netEl = document.getElementById('sec-net-qty');
    netEl.textContent = (netQty >= 0 ? '+' : '') + netQty;
    netEl.className = 'text-base font-bold ' + (netQty === 0 ? '' : netQty > 0 ? 'pnl-pos' : 'pnl-neg');
    const pnlEl = document.getElementById('sec-total-pnl');
    pnlEl.textContent = fmtPnlText(totalPairPnl);
    pnlEl.className = 'text-base font-bold ' + (totalPairPnl >= 0 ? 'pnl-pos' : 'pnl-neg');

    // Update dropdown options and render table
    updateSecFilterOptions();
    renderSecondaryOrders();
}

function updateSecFilterOptions() {
    const sel = document.getElementById('sec-filter');
    if (!sel) return;
    const current = sel.value;
    const syms = [...new Set(allSecOrdersCache.map(o => o.primary).filter(Boolean))].sort();
    const existing = Array.from(sel.options).map(o => o.value).filter(v => v !== 'ALL');
    if (JSON.stringify(syms) !== JSON.stringify(existing)) {
        sel.innerHTML = '<option value="ALL">All Primaries</option>';
        syms.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            sel.appendChild(opt);
        });
        sel.value = syms.includes(current) ? current : 'ALL';
    }
}

function renderSecondaryOrders() {
    const filter = document.getElementById('sec-filter').value;
    const filtered = filter === 'ALL' ? allSecOrdersCache : allSecOrdersCache.filter(o => o.primary === filter);
    const tbody = document.getElementById('sec-orders-tbody');
    const empty = document.getElementById('sec-orders-empty');
    if (filtered.length === 0) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
    } else {
        empty.style.display = 'none';
        tbody.innerHTML = filtered.map(o => {
            const roleCls = o.role === 'HEDGE'
                ? 'background:rgba(179,136,255,0.15);color:var(--purple);'
                : 'background:rgba(0,200,83,0.15);color:var(--green);';
            const sideCls = o.side === 'BUY' ? 'badge-buy' : 'badge-sell';
            return '<tr>' +
                '<td style="white-space:nowrap;">' + fmtTime(o.ts) + '</td>' +
                '<td class="font-bold">' + o.primary + '</td>' +
                '<td>' + (o.bot === 'A' ? 'A (Buy)' : 'B (Sell)') + '</td>' +
                '<td>L' + o.level + '</td>' +
                '<td><span class="status-badge" style="' + roleCls + '">' + o.role + '</span></td>' +
                '<td><span class="status-badge ' + sideCls + '">' + o.side + '</span></td>' +
                '<td>' + o.qty + '</td>' +
                '<td>' + (o.price ? o.price.toFixed(2) : '—') + '</td>' +
                '<td style="font-family:monospace;font-size:12px;">' + (o.xts_id || '—') + '</td>' +
                '<td style="font-family:monospace;font-size:12px;">' + (o.custom_id || '—') + '</td>' +
                '<td style="font-family:monospace;font-size:11px;color:var(--dim);">' + o.group_id + '</td>' +
                '</tr>';
        }).join('');
    }
}

// --- Render per-bot panel ---
function renderBotPanel(sym, data) {
    const s = data.summary || {};
    const state = data.state || {};
    const running = data.running;
    const cfg = data.config || {};
    const anchor = s.anchor_price || state.anchor_price || 0;

    // KPIs
    const statusEl = document.getElementById(sym + '-status');
    if (statusEl) {
        statusEl.innerHTML = running
            ? '<span class="status-badge badge-running" style="font-size:13px;">Running</span>'
            : '<span class="status-badge badge-stopped" style="font-size:13px;">Stopped</span>';
    }
    const anchorEl = document.getElementById(sym + '-anchor');
    if (anchorEl) anchorEl.textContent = anchor > 0 ? anchor.toFixed(2) : '—';
    const combEl = document.getElementById(sym + '-combined');
    if (combEl) {
        const comb = s.today_combined_pnl || 0;
        combEl.textContent = fmtPnlText(comb);
        combEl.className = 'text-base font-bold ' + (comb >= 0 ? 'pnl-pos' : 'pnl-neg');
    }
    const cycEl = document.getElementById(sym + '-cycles');
    if (cycEl) cycEl.textContent = s.today_cycles || 0;
    const owrEl = document.getElementById(sym + '-open-wr');
    if (owrEl) owrEl.textContent = (s.open_groups || 0) + ' / ' + (s.today_win_rate || 0).toFixed(1) + '%';

    // Epoch KPIs
    const buyLvlEl = document.getElementById(sym + '-buy-levels');
    if (buyLvlEl) buyLvlEl.textContent = s.buy_grid_levels || 0;
    const buySpcEl = document.getElementById(sym + '-buy-spacing');
    if (buySpcEl) buySpcEl.textContent = (s.current_buy_spacing || cfg.grid_space || 0.01).toFixed(4);
    const sellLvlEl = document.getElementById(sym + '-sell-levels');
    if (sellLvlEl) sellLvlEl.textContent = s.sell_grid_levels || 0;
    const sellSpcEl = document.getElementById(sym + '-sell-spacing');
    if (sellSpcEl) sellSpcEl.textContent = (s.current_sell_spacing || cfg.grid_space || 0.01).toFixed(4);

    // Grid levels
    const gridSpace = cfg.grid_space || 0.01;
    const targetOff = cfg.target || 0.03;
    const levelsPerSide = cfg.levels_per_side || 10;
    const qtyPerLevel = cfg.qty_per_level || 100;
    const buySpacing = s.current_buy_spacing || gridSpace;
    const sellSpacing = s.current_sell_spacing || gridSpace;
    const grid = computeGridLevels(anchor, gridSpace, targetOff, levelsPerSide, qtyPerLevel, buySpacing, sellSpacing);

    // Build index→status map from open groups
    const og = state.open_groups || {};
    const groupByLevel = {};
    Object.values(og).forEach(g => {
        const key = g.bot + ':' + g.subset_index;
        groupByLevel[key] = g;
    });

    // Buy grid
    const secSym = secondarySymbol || 'SPCENET';
    const buyGridEl = document.getElementById(sym + '-buy-grid');
    if (buyGridEl) {
        buyGridEl.innerHTML = grid.buy.map(lv => {
            const g = groupByLevel['A:' + lv.index];
            return renderGridLevel(lv, g, secSym, sym + '-buy');
        }).join('');
    }

    // Sell grid
    const sellGridEl = document.getElementById(sym + '-sell-grid');
    if (sellGridEl) {
        sellGridEl.innerHTML = grid.sell.map(lv => {
            const g = groupByLevel['B:' + lv.index];
            return renderGridLevel(lv, g, secSym, sym + '-sell');
        }).join('');
    }

    // Open positions
    const openTbody = document.getElementById(sym + '-open-tbody');
    const openEmpty = document.getElementById(sym + '-open-empty');
    const openGroups = Object.values(og).sort((a,b) => a.subset_index - b.subset_index);
    if (openTbody) {
        if (openGroups.length === 0) {
            openTbody.innerHTML = '';
            if (openEmpty) openEmpty.style.display = 'block';
        } else {
            if (openEmpty) openEmpty.style.display = 'none';
            openTbody.innerHTML = openGroups.map(g => {
                const statusCls = g.status === 'ENTRY_PENDING' ? 'badge-entry' : 'badge-target';
                return '<tr>' +
                    '<td>' + g.group_id + '</td>' +
                    '<td>' + (g.bot === 'A' ? '<span class="status-badge badge-buy">A (Buy)</span>' : '<span class="status-badge badge-sell">B (Sell)</span>') + '</td>' +
                    '<td>L' + g.subset_index + '</td>' +
                    '<td>' + g.entry_side + '</td>' +
                    '<td>' + g.entry_price.toFixed(2) + '</td>' +
                    '<td>' + (g.entry_fill_price ? g.entry_fill_price.toFixed(2) : '—') + '</td>' +
                    '<td>' + g.target_price.toFixed(2) + '</td>' +
                    '<td>' + g.qty + '</td>' +
                    '<td>' + (g.pair_hedged_qty || 0) + '</td>' +
                    '<td><span class="status-badge ' + statusCls + '">' + g.status.replace('_',' ') + '</span></td></tr>';
            }).join('');
        }
    }

    // Closed trades
    const closedTbody = document.getElementById(sym + '-closed-tbody');
    const closedEmpty = document.getElementById(sym + '-closed-empty');
    let closed = (state.closed_groups || []).slice().sort((a,b) => (b.closed_at || '').localeCompare(a.closed_at || '')).slice(0, 30);
    if (closedTbody) {
        if (closed.length === 0) {
            closedTbody.innerHTML = '';
            if (closedEmpty) closedEmpty.style.display = 'block';
        } else {
            if (closedEmpty) closedEmpty.style.display = 'none';
            const rows = [];
            closed.forEach(g => {
                const botLabel = g.bot === 'A' ? 'A' : 'B';
                const isBuy = g.entry_side === 'BUY';
                const buyP = isBuy ? (g.entry_fill_price || g.entry_price) : (g.target_fill_price || g.target_price);
                const sellP = isBuy ? (g.target_fill_price || g.target_price) : (g.entry_fill_price || g.entry_price);
                const status = g.status || 'CLOSED';
                const typeLabel = status === 'CANCELLED'
                    ? '<span class="status-badge badge-entry">CANCELLED</span>'
                    : '<span class="status-badge badge-closed">CYCLE</span>';
                rows.push('<tr>' +
                    '<td>' + g.group_id + '</td>' +
                    '<td>' + botLabel + '</td>' +
                    '<td>L' + g.subset_index + '</td>' +
                    '<td>' + typeLabel + '</td>' +
                    '<td>' + (buyP ? buyP.toFixed(2) : '—') + '</td>' +
                    '<td>' + (sellP ? sellP.toFixed(2) : '—') + '</td>' +
                    '<td>' + g.qty + '</td>' +
                    '<td>' + fmtPnl(g.realized_pnl) + '</td>' +
                    '<td>' + fmtTime(g.closed_at) + '</td></tr>');
                // Hedge sub-row
                const hedgePrice = g.pair_hedge_price || (g.pair_hedged_qty > 0 ? g.pair_hedge_vwap : null);
                const unwindPrice = g.pair_unwind_price || (g.pair_unwound_qty > 0 ? g.pair_unwind_vwap : null);
                const hedgeQty = g.pair_hedged_qty || (g.pair_hedge_price ? g.qty : 0);
                if (hedgePrice) {
                    const hBuy = isBuy ? unwindPrice : hedgePrice;
                    const hSell = isBuy ? hedgePrice : unwindPrice;
                    rows.push('<tr style="background:rgba(179,136,255,0.04);">' +
                        '<td style="color:var(--purple);padding-left:16px;">&#8627; ' + secondarySymbol + '</td>' +
                        '<td style="color:var(--dim);">' + botLabel + '</td>' +
                        '<td style="color:var(--dim);">L' + g.subset_index + '</td>' +
                        '<td><span class="status-badge" style="background:rgba(179,136,255,0.15);color:var(--purple);">HEDGE</span></td>' +
                        '<td>' + (hBuy ? hBuy.toFixed(2) : '—') + '</td>' +
                        '<td>' + (hSell ? hSell.toFixed(2) : '—') + '</td>' +
                        '<td>' + hedgeQty + '</td>' +
                        '<td>' + fmtPnl(g.pair_pnl) + '</td>' +
                        '<td style="color:var(--dim);">' + fmtTime(g.closed_at) + '</td></tr>');
                }
            });
            closedTbody.innerHTML = rows.join('');
        }
    }
}

// --- Round trips filter & render ---
function updateRtFilterOptions() {
    const sel = document.getElementById('rt-filter');
    const current = sel.value;
    const syms = [...new Set(allCyclesCache.map(g => g._primary).filter(Boolean))].sort();
    // Rebuild options only if primaries changed
    const existing = Array.from(sel.options).map(o => o.value).filter(v => v !== 'ALL');
    if (JSON.stringify(syms) !== JSON.stringify(existing)) {
        sel.innerHTML = '<option value="ALL">All Primaries</option>';
        syms.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            sel.appendChild(opt);
        });
        sel.value = syms.includes(current) ? current : 'ALL';
    }
}

function renderRoundTrips() {
    const filter = document.getElementById('rt-filter').value;
    const filtered = filter === 'ALL' ? allCyclesCache : allCyclesCache.filter(g => g._primary === filter);
    const rtTbody = document.getElementById('roundtrips-tbody');
    const rtEmpty = document.getElementById('roundtrips-empty');
    if (filtered.length === 0) {
        rtTbody.innerHTML = '';
        rtEmpty.style.display = 'block';
    } else {
        rtEmpty.style.display = 'none';
        rtTbody.innerHTML = filtered.slice(0, 50).map(g => {
            const isBuy = g.entry_side === 'BUY';
            const entryP = g.entry_fill_price || g.entry_price;
            const exitP = g.target_fill_price || g.target_price;
            const primaryPnl = g.realized_pnl || 0;
            const pairPnl = g.pair_pnl || 0;
            const combinedPnl = primaryPnl + pairPnl;
            const sideBadge = isBuy
                ? '<span class="status-badge badge-buy">BUY</span>'
                : '<span class="status-badge badge-sell">SELL</span>';
            return '<tr>' +
                '<td style="font-family:monospace;font-size:11px;color:var(--cyan);">' + (g.group_id || '\\u2014') + '</td>' +
                '<td class="font-bold">' + (g._primary || '') + '</td>' +
                '<td>' + (g.bot === 'A' ? 'A' : 'B') + '</td>' +
                '<td>L' + g.subset_index + '</td>' +
                '<td>' + sideBadge + '</td>' +
                '<td>' + (entryP ? entryP.toFixed(2) : '\\u2014') + '</td>' +
                '<td>' + (exitP ? exitP.toFixed(2) : '\\u2014') + '</td>' +
                '<td>' + g.qty + '</td>' +
                '<td>' + fmtPnl(primaryPnl) + '</td>' +
                '<td>' + fmtPnl(pairPnl) + '</td>' +
                '<td>' + fmtPnl(combinedPnl) + '</td>' +
                '<td style="white-space:nowrap;">' + fmtTime(g.closed_at) + '</td></tr>';
        }).join('');
    }
}

// --- Config load ---
function loadConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            currentConfig = cfg;
            secondarySymbol = cfg.secondary_symbol || 'SPCENET';
            document.getElementById('hdr-secondary').textContent = 'Secondary: ' + secondarySymbol;
            const primaries = (cfg.primaries || []).map(p => p.symbol).filter(Boolean);
            if (JSON.stringify(primaries) !== JSON.stringify(knownPrimaries)) {
                buildTabs(primaries);
                // Restore active tab
                if (primaries.includes(activeTab)) switchTab(activeTab);
            }
        })
        .catch(e => console.error('Config error:', e));
}

// --- Status indicator ---
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
    document.getElementById('hdr-time').textContent = new Date().toLocaleTimeString('en-IN',
        {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}

// --- Main update ---
function updateMonitor() {
    fetch('/api/state')
        .then(r => r.json())
        .then(allStates => {
            allStatesCache = allStates;
            let aggPrimary = 0, aggPair = 0, aggCycles = 0, aggOpen = 0;
            const breakdownRows = [];
            let allClosed = [];

            for (const [sym, data] of Object.entries(allStates)) {
                const s = data.summary || {};
                const state = data.state || {};
                const running = data.running;
                botStatuses[sym] = running;

                // Use today-only metrics
                const primaryPnl = s.today_primary_pnl || 0;
                const pairPnl = s.today_pair_pnl || 0;
                const combined = s.today_combined_pnl || 0;
                const cycles = s.today_cycles || 0;
                const open = s.open_groups || 0;
                const winRate = s.today_win_rate || 0;

                aggPrimary += primaryPnl;
                aggPair += pairPnl;
                aggCycles += cycles;
                aggOpen += open;

                const statusBadge = running
                    ? '<span class="status-badge badge-running">Running</span>'
                    : '<span class="status-badge badge-stopped">Stopped</span>';
                breakdownRows.push('<tr style="cursor:pointer;" onclick="switchTab(\\'' + sym + '\\')">' +
                    '<td class="font-bold">' + sym + '</td>' +
                    '<td>' + statusBadge + '</td>' +
                    '<td>' + (s.anchor_price || 0).toFixed(2) + '</td>' +
                    '<td>' + fmtPnl(primaryPnl) + '</td>' +
                    '<td>' + fmtPnl(pairPnl) + '</td>' +
                    '<td>' + fmtPnl(combined) + '</td>' +
                    '<td>' + cycles + '</td>' +
                    '<td>' + open + '</td>' +
                    '<td>' + winRate.toFixed(1) + '%</td></tr>');

                (state.closed_groups || []).forEach(g => { g._primary = sym; allClosed.push(g); });

                // Update per-bot panel if visible
                if (activeTab === sym) renderBotPanel(sym, data);
            }

            // Update secondary panel if visible
            if (activeTab === 'SECONDARY') renderSecondaryPanel(allStatesCache);

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

            breakdownRows.push('<tr style="border-top:2px solid var(--border);font-weight:bold;">' +
                '<td>TOTAL</td><td></td><td></td>' +
                '<td>' + fmtPnl(aggPrimary) + '</td><td>' + fmtPnl(aggPair) + '</td>' +
                '<td>' + fmtPnl(aggCombined) + '</td><td>' + aggCycles + '</td>' +
                '<td>' + aggOpen + '</td><td></td></tr>');
            document.getElementById('breakdown-tbody').innerHTML = breakdownRows.join('');

            // Round trips — cache cycles and update dropdown options
            allCyclesCache = allClosed.filter(g => g.status !== 'CANCELLED')
                .sort((a,b) => (b.closed_at || '').localeCompare(a.closed_at || ''));
            updateRtFilterOptions();
            renderRoundTrips();

            // PnL chart
            allClosed.sort((a,b) => (a.closed_at || '').localeCompare(b.closed_at || ''));
            if (allClosed.length > 0) {
                let cumPrimary = 0, cumCombined = 0;
                const labels = [], primaryData = [], combinedData = [];
                allClosed.forEach((g, i) => {
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
                        labels,
                        datasets: [{
                            label: 'Primary PnL', data: primaryData,
                            borderColor: '#448aff', fill: false, tension: 0.3,
                            pointRadius: 0, borderWidth: 2,
                        }, {
                            label: 'Combined PnL', data: combinedData,
                            borderColor: combinedData[combinedData.length-1] >= 0 ? '#00c853' : '#ff1744',
                            backgroundColor: (combinedData[combinedData.length-1] >= 0 ? 'rgba(0,200,83,' : 'rgba(255,23,68,') + '0.1)',
                            fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { legend: { display: true, labels: { color: '#aaa' } } },
                        scales: {
                            x: { display: true, title: { display: true, text: 'Trade #', color: '#888' },
                                 ticks: { color: '#888', maxTicksLimit: 15 }, grid: { color: 'rgba(42,45,58,0.5)' } },
                            y: { display: true, title: { display: true, text: 'PnL', color: '#888' },
                                 ticks: { color: '#888' }, grid: { color: 'rgba(42,45,58,0.5)' } }
                        }
                    }
                });
            }

            updateStatusIndicator();
        })
        .catch(e => console.error('Monitor error:', e));
}

// --- Init ---
loadConfig();
setInterval(loadConfig, 30000);
setInterval(updateMonitor, 3000);
setTimeout(updateMonitor, 500);
</script>
</body>
</html>'''


def _build_config_html() -> str:
    """Build the config dashboard HTML (port 7779)."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Grid Bot Config Panel</title>
<script src="https://cdn.tailwindcss.com"></script>
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
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 6px; animation: pulse 2s ease-in-out infinite;
    }
    .pulse-green { background: var(--green); }
    .pulse-red { background: var(--red); }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .status-badge {
        display: inline-block; padding: 2px 6px; border-radius: 4px;
        font-size: 10px; font-weight: 600;
    }
    .badge-running { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-stopped { background: rgba(255,23,68,0.15); color: var(--red); }
    input, select {
        background: #0f1117; border: 1px solid var(--border); color: var(--text);
        padding: 6px 10px; border-radius: 4px; font-family: inherit; font-size: 12px;
        width: 100%;
    }
    input:focus, select:focus { outline: 1px solid var(--blue); }
    button {
        font-family: inherit; font-size: 12px; cursor: pointer; border: none;
        border-radius: 4px; padding: 6px 14px; font-weight: 600;
        transition: opacity 0.15s;
    }
    button:hover { opacity: 0.85; }
    .btn-green { background: var(--green); color: #000; }
    .btn-red { background: var(--red); color: #fff; }
    .btn-blue { background: var(--blue); color: #fff; }
    .btn-dim { background: var(--border); color: var(--text); }
    .btn-orange { background: var(--orange); color: #000; }
    .field-hint {
        font-size: 10px; color: var(--dim); margin-top: 2px; line-height: 1.3;
    }
</style>
</head>
<body class="p-4 max-w-4xl mx-auto">

<!-- HEADER -->
<div class="flex justify-between items-center p-3 rounded-lg mb-4" style="background:var(--card);border:1px solid var(--border);">
    <div>
        <h1 class="text-lg font-bold">TG GRID BOT CONFIG PANEL</h1>
        <span style="color:var(--dim);font-size:12px;">Manage primaries, parameters, and bot processes</span>
    </div>
    <div class="text-right" style="font-size:12px;">
        <span class="pulse pulse-green" id="status-pulse"></span>
        <span id="status-text">Loading...</span><br>
        <span style="color:var(--dim);" id="hdr-time">--</span>
    </div>
</div>

<!-- SAVE STATUS TOAST -->
<div id="toast" class="fixed top-4 right-4 px-4 py-2 rounded-lg text-sm font-semibold" style="background:var(--green);color:#000;display:none;z-index:100;">Saved</div>

<!-- GLOBAL SETTINGS -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Global Settings</h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Secondary Symbol</label>
            <input id="cfg-secondary" value="SPCENET">
            <div class="field-hint">Pair hedge symbol for all primaries</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Zerodha User</label>
            <input id="cfg-zerodha-user" value="Sai">
            <div class="field-hint">Market data source</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS API Key</label>
            <input id="cfg-xts-key" style="font-size:10px;">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Root URL</label>
            <input id="cfg-xts-root" style="font-size:10px;">
        </div>
    </div>
</div>

<!-- PRIMARY CONFIGS -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <div class="flex justify-between items-center mb-3">
        <h2 class="text-sm font-semibold" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Primary Symbols</h2>
        <button class="btn-blue text-xs" onclick="addPrimary()">+ Add Primary</button>
    </div>
    <div id="primaries-container"></div>
</div>

<!-- ACTION BUTTONS -->
<div class="flex gap-2 mb-4">
    <button class="btn-green" onclick="saveConfig()">Save Config</button>
    <button class="btn-dim" onclick="loadConfig()">Reload</button>
    <button class="btn-red" onclick="stopAllBots()" style="margin-left:auto;">Stop All Bots</button>
</div>

<!-- EDIT MODAL -->
<div id="edit-modal" class="fixed inset-0 flex items-center justify-center" style="background:rgba(0,0,0,0.7);display:none;z-index:50;">
    <div class="rounded-lg p-6 w-full max-w-xl" style="background:var(--card);border:1px solid var(--border);">
        <h3 class="text-base font-semibold mb-4" id="modal-title">Edit Primary</h3>
        <div class="grid grid-cols-2 gap-x-4 gap-y-3">
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Symbol</label>
                <input id="m-symbol">
                <div class="field-hint">NSE trading symbol (e.g. TATSILV)</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Product</label>
                <select id="m-product">
                    <option value="NRML">NRML (carry-forward)</option>
                    <option value="MIS">MIS (intraday)</option>
                </select>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Grid Space (INR)</label>
                <input id="m-grid-space" type="number" step="0.01">
                <div class="field-hint">Distance between grid levels</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Target (INR)</label>
                <input id="m-target" type="number" step="0.01">
                <div class="field-hint">Profit target per level</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Levels Per Side</label>
                <input id="m-levels-per-side" type="number">
                <div class="field-hint">Grid levels on each side before reanchor</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Qty Per Level</label>
                <input id="m-qty-per-level" type="number">
                <div class="field-hint">Shares per grid level order</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Hedge Ratio</label>
                <input id="m-hedge-ratio" type="number">
                <div class="field-hint">Secondary shares per primary on COMPLETE fill (0=disabled)</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Partial Hedge Ratio</label>
                <input id="m-partial-hedge-ratio" type="number">
                <div class="field-hint">Secondary shares per primary on PARTIAL fill (0=disabled)</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Holdings Override</label>
                <input id="m-holdings" type="number">
                <div class="field-hint">SellBot available shares. -1=use broker API, 0+=override</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Reanchor Epoch</label>
                <input id="m-reanchor-epoch" type="number">
                <div class="field-hint">Reanchors before spacing increases</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Max Grid Levels</label>
                <input id="m-max-grid-levels" type="number">
                <div class="field-hint">Stop bot after N grid levels on one side</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Poll Interval (s)</label>
                <input id="m-poll" type="number" step="0.5">
                <div class="field-hint">Order status check frequency</div>
            </div>
            <div>
                <label class="block text-xs mb-1" style="color:var(--dim);">Anchor Price</label>
                <input id="m-anchor" type="number" step="0.01">
                <div class="field-hint">Grid center price (0 if auto)</div>
            </div>
            <div class="flex flex-col justify-center">
                <label class="flex items-center gap-2 text-xs cursor-pointer" style="color:var(--text);">
                    <input type="checkbox" id="m-auto-anchor" style="width:auto;"> Auto Anchor (use LTP)
                </label>
                <div class="field-hint mt-1">Fetch current price from Zerodha on start</div>
            </div>
        </div>
        <div class="flex gap-2 mt-5 justify-end">
            <button class="btn-dim" onclick="closeModal()">Cancel</button>
            <button class="btn-green" onclick="saveModal()">Save</button>
        </div>
    </div>
</div>

<script>
let currentConfig = {};
let editingIdx = -1;
let botStatuses = {};
let botPids = {};

function showToast(msg, color) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.style.background = color || 'var(--green)';
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 2000);
}

// --- Config ---
function loadConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            currentConfig = cfg;
            document.getElementById('cfg-secondary').value = cfg.secondary_symbol || '';
            document.getElementById('cfg-zerodha-user').value = cfg.zerodha_user || 'Sai';
            document.getElementById('cfg-xts-key').value = cfg.xts_interactive_key || '';
            document.getElementById('cfg-xts-root').value = cfg.xts_root || '';
            renderPrimaries();
        })
        .catch(e => console.error('Load config error:', e));
}

function saveConfig() {
    currentConfig.secondary_symbol = document.getElementById('cfg-secondary').value.trim();
    currentConfig.zerodha_user = document.getElementById('cfg-zerodha-user').value.trim();
    currentConfig.xts_interactive_key = document.getElementById('cfg-xts-key').value.trim();
    currentConfig.xts_root = document.getElementById('cfg-xts-root').value.trim();
    fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(currentConfig),
    })
    .then(r => r.json())
    .then(r => {
        if (r.status === 'ok') showToast('Config saved');
        else showToast('Save failed: ' + (r.error || ''), 'var(--red)');
    })
    .catch(e => showToast('Save error', 'var(--red)'));
}

// --- Primaries ---
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
        const pid = botPids[sym] || '';
        const statusBadge = running
            ? '<span class="status-badge badge-running">Running' + (pid ? ' (PID ' + pid + ')' : '') + '</span>'
            : '<span class="status-badge badge-stopped">Stopped</span>';
        const startStopBtn = running
            ? `<button class="btn-red text-xs" onclick="stopBot('${sym}')">Stop</button>`
            : `<button class="btn-green text-xs" onclick="startBot('${sym}')">Start</button>`;
        const anchor = p.auto_anchor ? 'Auto (LTP)' : (p.anchor_price || 'N/A');
        return `
        <div class="rounded p-3 mb-2" style="background:#0f1117;border:1px solid var(--border);">
            <div class="flex justify-between items-center mb-2">
                <div>
                    <span class="font-bold text-sm" style="color:var(--blue);">${sym}</span> ${statusBadge}
                </div>
                <div class="flex gap-1">
                    ${startStopBtn}
                    <button class="btn-blue text-xs" onclick="editPrimary(${i})">Edit</button>
                    <button class="btn-dim text-xs" onclick="removePrimary(${i})">Remove</button>
                </div>
            </div>
            <div class="grid grid-cols-4 gap-x-4 gap-y-1 text-xs" style="color:var(--dim);">
                <div>Anchor: <span style="color:var(--text);">${anchor}</span></div>
                <div>Space: <span style="color:var(--text);">${p.grid_space}</span></div>
                <div>Target: <span style="color:var(--text);">${p.target}</span></div>
                <div>Product: <span style="color:var(--text);">${p.product || 'NRML'}</span></div>
                <div>Levels/Side: <span style="color:var(--text);">${p.levels_per_side || 10}</span></div>
                <div>Qty/Level: <span style="color:var(--text);">${p.qty_per_level || 100}</span></div>
                <div>Hedge: <span style="color:var(--text);">${p.hedge_ratio}</span></div>
                <div>Partial: <span style="color:var(--text);">${p.partial_hedge_ratio}</span></div>
                <div>Holdings: <span style="color:var(--text);">${p.holdings_override}</span></div>
                <div>Epoch: <span style="color:var(--text);">${p.reanchor_epoch || 100}</span></div>
                <div>Max Levels: <span style="color:var(--text);">${p.max_grid_levels || 2000}</span></div>
                <div>Poll: <span style="color:var(--text);">${p.poll_interval}s</span></div>
            </div>
        </div>`;
    }).join('');
}

function addPrimary() {
    if (!currentConfig.primaries) currentConfig.primaries = [];
    currentConfig.primaries.push({
        symbol: '', enabled: true, auto_anchor: true, anchor_price: 0,
        grid_space: 0.01, target: 0.03, levels_per_side: 10, qty_per_level: 100,
        hedge_ratio: 1, partial_hedge_ratio: 1, holdings_override: 2000,
        product: 'NRML', poll_interval: 2.0, reanchor_epoch: 100, max_grid_levels: 2000,
    });
    editPrimary(currentConfig.primaries.length - 1);
}

function removePrimary(idx) {
    const sym = currentConfig.primaries[idx].symbol || 'this primary';
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
    document.getElementById('m-levels-per-side').value = p.levels_per_side || 10;
    document.getElementById('m-qty-per-level').value = p.qty_per_level || 100;
    document.getElementById('m-hedge-ratio').value = p.hedge_ratio || 0;
    document.getElementById('m-partial-hedge-ratio').value = p.partial_hedge_ratio || 0;
    document.getElementById('m-holdings').value = p.holdings_override != null ? p.holdings_override : -1;
    document.getElementById('m-reanchor-epoch').value = p.reanchor_epoch != null ? p.reanchor_epoch : 100;
    document.getElementById('m-max-grid-levels').value = p.max_grid_levels != null ? p.max_grid_levels : 2000;
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
    p.levels_per_side = parseInt(document.getElementById('m-levels-per-side').value);
    p.qty_per_level = parseInt(document.getElementById('m-qty-per-level').value);
    p.hedge_ratio = parseInt(document.getElementById('m-hedge-ratio').value);
    p.partial_hedge_ratio = parseInt(document.getElementById('m-partial-hedge-ratio').value);
    p.holdings_override = parseInt(document.getElementById('m-holdings').value);
    p.reanchor_epoch = parseInt(document.getElementById('m-reanchor-epoch').value);
    p.max_grid_levels = parseInt(document.getElementById('m-max-grid-levels').value);
    p.poll_interval = parseFloat(document.getElementById('m-poll').value);
    p.anchor_price = parseFloat(document.getElementById('m-anchor').value);
    p.auto_anchor = document.getElementById('m-auto-anchor').checked;
    closeModal();
    renderPrimaries();
}

// --- Bot control ---
function startBot(symbol) {
    fetch('/api/bot/start/' + symbol, {method: 'POST'})
        .then(r => r.json())
        .then(r => {
            if (r.status === 'started') showToast(symbol + ' started');
            else showToast(r.error || 'Failed', 'var(--red)');
            updateProcesses();
        })
        .catch(e => showToast('Start error', 'var(--red)'));
}

function stopBot(symbol) {
    fetch('/api/bot/stop/' + symbol, {method: 'POST'})
        .then(r => r.json())
        .then(r => {
            if (r.status === 'stopped') showToast(symbol + ' stopped');
            else showToast(r.error || 'Not running', 'var(--orange)');
            updateProcesses();
        })
        .catch(e => showToast('Stop error', 'var(--red)'));
}

function stopAllBots() {
    if (!confirm('Stop ALL running bots?')) return;
    fetch('/api/bot/stop-all', {method: 'POST'})
        .then(r => r.json())
        .then(r => { showToast('All bots stopped'); updateProcesses(); })
        .catch(e => showToast('Error', 'var(--red)'));
}

function updateProcesses() {
    fetch('/api/processes')
        .then(r => r.json())
        .then(procs => {
            botStatuses = {};
            botPids = {};
            for (const [sym, info] of Object.entries(procs)) {
                botStatuses[sym] = info.running;
                if (info.running) botPids[sym] = info.pid;
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
    document.getElementById('hdr-time').textContent = new Date().toLocaleTimeString('en-IN',
        {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}

// --- Init ---
loadConfig();
updateProcesses();
setInterval(updateProcesses, 5000);
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='TG Grid Bot Dashboard')
    parser.add_argument('--port', type=int, default=7777, help='Dashboard port (default: 7777)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    parser.add_argument('--mode', default='monitor', choices=['monitor', 'config'],
                        help='Dashboard mode: monitor (7777) or config (7779)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    # Ensure config exists
    if not os.path.exists(CONFIG_FILE):
        _save_config(_DEFAULT_CONFIG)

    app = create_app(mode=args.mode)

    # Cleanup on exit
    import atexit
    atexit.register(_stop_all_bots)

    logger.info("Starting TG Dashboard (%s) on %s:%d", args.mode, args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
