"""
TollGate Dashboard — Monitor (7788) + Config (7786) web UI.

Features:
- Monitor mode (--mode monitor, port 7788): Live grid visualization, PnL, inventory
- Config mode (--mode config, port 7786): Edit config, start/stop bot
- Shared backend: State, config, and process management APIs

Usage:
    python -m TG.TollGate.run --dashboard --mode monitor --port 7788
    python -m TG.TollGate.run --dashboard --mode config --port 7786
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

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATE_DIR = os.path.join(os.path.dirname(__file__), 'state')
CONFIG_FILE = os.path.join(STATE_DIR, 'tollgate_config.json')
PID_FILE = os.path.join(STATE_DIR, '.bot_pids.json')

_DEFAULT_CONFIG = {
    "symbol": "SPCENET",
    "base_spacing": 0.01,
    "round_trip_profit": 0.01,
    "levels_per_side": 10,
    "qty_per_level": 4000,
    "amount_per_level": 0,
    "disclosed_pct": 0,
    "max_reanchors": 100,
    "product": "CNC",
    "poll_interval": 2.0,
    "interactive_key": "1d17edd135146be7572510",
    "interactive_secret": "Htvy720#4K",
    "marketdata_key": "202e06ba0b421bf9e1e515",
    "marketdata_secret": "Payr544@nk",
    "xts_root": "https://xts.myfindoc.com",
    "auto_anchor": True,
    "anchor_price": 0,
}


def _load_bot_pids() -> Dict[str, int]:
    if not os.path.exists(PID_FILE):
        return {}
    try:
        with open(PID_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_bot_pids(pids: Dict[str, int]):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = PID_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(pids, f, indent=2)
    os.replace(tmp, PID_FILE)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _load_config() -> dict:
    os.makedirs(STATE_DIR, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to load config: %s", e)
    return _DEFAULT_CONFIG.copy()


def _save_config(config: dict):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(config, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def _load_state() -> dict:
    path = os.path.join(STATE_DIR, 'SPCENET_tollgate_state.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load state: %s", e)
        return {}


def _is_bot_running() -> bool:
    pids = _load_bot_pids()
    pid = pids.get('SPCENET')
    if pid is None:
        return False
    if _pid_alive(pid):
        return True
    pids.pop('SPCENET', None)
    _save_bot_pids(pids)
    return False


def _get_bot_pid() -> Optional[int]:
    pids = _load_bot_pids()
    pid = pids.get('SPCENET')
    if pid and _pid_alive(pid):
        return pid
    return None


def _start_bot(config: dict) -> bool:
    if _is_bot_running():
        return False

    cmd = [
        sys.executable, '-m', 'TG.TollGate.run',
        '--interactive-key', config.get('interactive_key', ''),
        '--interactive-secret', config.get('interactive_secret', ''),
        '--marketdata-key', config.get('marketdata_key', ''),
        '--marketdata-secret', config.get('marketdata_secret', ''),
        '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
        '--spacing', str(config.get('base_spacing', 0.01)),
        '--profit', str(config.get('round_trip_profit', 0.01)),
        '--levels', str(config.get('levels_per_side', 10)),
        '--qty', str(config.get('qty_per_level', 4000)),
        '--product', config.get('product', 'NRML'),
        '--poll-interval', str(config.get('poll_interval', 2.0)),
        '--max-reanchors', str(config.get('max_reanchors', 100)),
    ]

    if config.get('amount_per_level', 0) > 0:
        cmd.extend(['--amount', str(config['amount_per_level'])])
    if config.get('disclosed_pct', 0) > 0:
        cmd.extend(['--disclosed-pct', str(config['disclosed_pct'])])

    if config.get('auto_anchor'):
        cmd.append('--auto-anchor')
    else:
        anchor = config.get('anchor_price', 0)
        if anchor > 0:
            cmd.extend(['--anchor', str(anchor)])
        else:
            cmd.append('--auto-anchor')

    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'tollgate_engine.log')

    with open(log_file, 'a') as lf:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT,
            stdout=lf, stderr=subprocess.STDOUT,
        )

    pids = _load_bot_pids()
    pids['SPCENET'] = proc.pid
    _save_bot_pids(pids)
    logger.info("Started TollGate bot: PID=%d", proc.pid)
    return True


def _stop_bot() -> bool:
    pids = _load_bot_pids()
    pid = pids.get('SPCENET')
    if pid is None:
        return False
    if not _pid_alive(pid):
        pids.pop('SPCENET', None)
        _save_bot_pids(pids)
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.5)
            if not _pid_alive(pid):
                break
        else:
            os.kill(pid, signal.SIGKILL)
        logger.info("Stopped TollGate bot (PID=%d)", pid)
    except ProcessLookupError:
        pass
    except Exception as e:
        logger.error("Error stopping bot (PID=%d): %s", pid, e)

    pids.pop('SPCENET', None)
    _save_bot_pids(pids)
    return True


def _compute_summary(state: dict) -> dict:
    if not state:
        return {}

    open_groups = state.get('open_groups', {})
    closed_groups = state.get('closed_groups', [])

    bot_a_ep = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'ENTRY_PENDING')
    bot_a_pa = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'ENTRY_PARTIAL')
    bot_a_tp = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'TARGET_PENDING')
    bot_b_ep = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'ENTRY_PENDING')
    bot_b_pa = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'ENTRY_PARTIAL')
    bot_b_tp = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'TARGET_PENDING')

    wins = sum(1 for g in closed_groups if g.get('realized_pnl', 0) > 0)
    win_rate = (wins / len(closed_groups) * 100) if closed_groups else 0.0

    # Compute Buy VWAP and Sell VWAP for today only
    # Filter groups by created_at date to today
    # Buy VWAP = VWAP of all shares we BOUGHT (buy entries + sell targets)
    # Sell VWAP = VWAP of all shares we SOLD (sell entries + buy targets)
    buy_cost, buy_qty = 0.0, 0
    sell_cost, sell_qty = 0.0, 0

    today_str = datetime.now().strftime('%Y-%m-%d')
    all_groups = list(open_groups.values()) + closed_groups
    for g in all_groups:
        created = g.get('created_at', '')
        if not created or created[:10] != today_str:
            continue
        entry_side = g.get('entry_side', '')
        efp = g.get('entry_fill_price', 0) or 0
        efsf = g.get('entry_filled_so_far', 0) or 0

        if entry_side == 'BUY' and efsf > 0 and efp > 0:
            buy_cost += efp * efsf
            buy_qty += efsf
        elif entry_side == 'SELL' and efsf > 0 and efp > 0:
            sell_cost += efp * efsf
            sell_qty += efsf

        for t in g.get('target_orders', []):
            tfq = t.get('filled_qty', 0) or 0
            tfp = t.get('fill_price', 0) or 0
            if tfq > 0 and tfp > 0:
                if entry_side == 'BUY':
                    sell_cost += tfp * tfq
                    sell_qty += tfq
                elif entry_side == 'SELL':
                    buy_cost += tfp * tfq
                    buy_qty += tfq

    buy_vwap = round(buy_cost / buy_qty, 4) if buy_qty > 0 else None
    sell_vwap = round(sell_cost / sell_qty, 4) if sell_qty > 0 else None
    spread = round(sell_vwap - buy_vwap, 4) if (buy_vwap and sell_vwap) else None

    # Compute realized PnL including partial fills from open groups
    # total_pnl only counts fully completed cycles; we add open group realized_pnl
    engine_pnl = state.get('total_pnl', 0)
    open_partial_pnl = sum(g.get('realized_pnl', 0) or 0 for g in open_groups.values())
    closed_partial_pnl = sum(g.get('realized_pnl', 0) or 0
                             for g in closed_groups if g.get('status') != 'CLOSED')
    total_realized_pnl = round(engine_pnl + open_partial_pnl + closed_partial_pnl, 2)

    return {
        'symbol': state.get('symbol', 'SPCENET'),
        'anchor_price': state.get('anchor_price', 0),
        'total_pnl': total_realized_pnl,
        'engine_pnl': round(engine_pnl, 2),
        'total_cycles': state.get('total_cycles', 0),
        'current_spacing': state.get('current_spacing', 0),
        'net_inventory': state.get('net_inventory', 0),
        'buy_reanchor_count': state.get('buy_reanchor_count', 0),
        'sell_reanchor_count': state.get('sell_reanchor_count', 0),
        'total_reanchors': state.get('total_reanchors', 0),
        'open_groups': len(open_groups),
        'win_rate': round(win_rate, 1),
        'bot_a': {'entry_pending': bot_a_ep, 'partial': bot_a_pa, 'target_pending': bot_a_tp},
        'bot_b': {'entry_pending': bot_b_ep, 'partial': bot_b_pa, 'target_pending': bot_b_tp},
        'buy_vwap': buy_vwap,
        'sell_vwap': sell_vwap,
        'spread': spread,
        'buy_fill_qty': buy_qty,
        'sell_fill_qty': sell_qty,
        'last_updated': state.get('last_updated', ''),
    }


def create_app(mode: str = 'monitor') -> Flask:
    """Create Flask app. mode='monitor' for 7788, mode='config' for 7786."""
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

    @app.route('/api/state')
    def api_state():
        state = _load_state()
        config = _load_config()
        return jsonify({
            'state': state,
            'summary': _compute_summary(state),
            'running': _is_bot_running(),
            'pid': _get_bot_pid(),
            'config': config,
        })

    @app.route('/api/bot/start', methods=['POST'])
    def api_start_bot():
        config = _load_config()
        if _start_bot(config):
            return jsonify({'status': 'started'})
        return jsonify({'error': 'Failed to start or already running'}), 400

    @app.route('/api/bot/stop', methods=['POST'])
    def api_stop_bot():
        if _stop_bot():
            return jsonify({'status': 'stopped'})
        return jsonify({'error': 'Not running'}), 400

    @app.route('/api/processes')
    def api_processes():
        pid = _get_bot_pid()
        return jsonify({
            'SPCENET': {
                'pid': pid,
                'running': pid is not None,
            }
        })

    @app.route('/')
    def index():
        if mode == 'config':
            return Response(_build_config_html(), mimetype='text/html')
        return Response(_build_monitor_html(), mimetype='text/html')

    return app


def _build_monitor_html() -> str:
    """Build the TollGate monitor dashboard HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TollGate Monitor — SPCENET</title>
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
    .badge-partial { background: rgba(179,136,255,0.15); color: var(--purple); }
    .badge-target { background: rgba(68,138,255,0.15); color: var(--blue); }
    .badge-closed { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-buy { background: rgba(0,200,83,0.10); color: var(--green); }
    .badge-sell { background: rgba(255,23,68,0.10); color: var(--red); }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th {
        text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border);
        color: var(--dim); font-weight: 500; font-size: 11px; text-transform: uppercase;
    }
    td { padding: 5px 8px; border-bottom: 1px solid #1e2130; }
    tr:hover td { background: rgba(68,138,255,0.05); }
    .grid-row-active { background: rgba(68,138,255,0.08); }
    .grid-row-filled { background: rgba(0,200,83,0.08); }
    .grid-row-partial { background: rgba(179,136,255,0.08); }
    .grid-main-row { cursor: pointer; }
    .grid-main-row:hover td { background: rgba(68,138,255,0.10); }
    .grid-sub-row td { padding: 2px 8px 2px 24px; font-size: 11px; color: var(--dim); border-bottom: 1px solid rgba(30,33,48,0.5); }
    .grid-sub-row.hidden { display: none; }
    .grid-sub-label { display: inline-block; width: 56px; font-weight: 600; text-transform: uppercase; font-size: 10px; letter-spacing: 0.3px; }
    .grid-sub-label.entry-label { color: var(--blue); }
    .grid-sub-label.target-label { color: var(--orange); }
    .grid-sub-label.reentry-label { color: var(--cyan); }
    .grid-sub-label.final-label { color: var(--green); }
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
        <h1 class="text-lg font-bold">TOLLGATE MARKET-MAKER — SPCENET</h1>
        <span style="color:var(--dim);font-size:12px;">Single-ticker grid market-making</span>
    </div>
    <div class="text-right" style="font-size:12px;">
        <span class="pulse pulse-red" id="status-pulse"></span>
        <span id="status-text">Loading...</span><br>
        <span style="color:var(--dim);" id="hdr-time">—</span>
    </div>
</div>

<!-- KPI CARDS ROW 1 -->
<div class="grid grid-cols-2 md:grid-cols-6 gap-3 mb-3">
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Realized PnL</div>
        <div class="text-xl font-bold" id="kpi-pnl">—</div>
        <div class="text-xs mt-1" style="color:var(--dim);" id="kpi-engine-pnl"></div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Cycles</div>
        <div class="text-xl font-bold" style="color:var(--blue);" id="kpi-cycles">—</div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Anchor</div>
        <div class="text-xl font-bold" style="color:var(--cyan);" id="kpi-anchor">—</div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Spacing</div>
        <div class="text-xl font-bold" style="color:var(--orange);" id="kpi-spacing">—</div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Net Inventory</div>
        <div class="text-xl font-bold" id="kpi-inventory">—</div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Reanchors</div>
        <div class="text-xl font-bold" style="color:var(--purple);" id="kpi-reanchors">—</div>
    </div>
</div>
<!-- KPI CARDS ROW 2: TODAY VWAP -->
<div class="grid grid-cols-3 gap-3 mb-4">
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Today Buy VWAP</div>
        <div class="text-lg font-bold" style="color:var(--green);" id="kpi-buy-vwap">—</div>
        <div class="text-xs mt-1" style="color:var(--dim);" id="kpi-buy-qty"></div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Today Sell VWAP</div>
        <div class="text-lg font-bold" style="color:var(--red);" id="kpi-sell-vwap">—</div>
        <div class="text-xs mt-1" style="color:var(--dim);" id="kpi-sell-qty"></div>
    </div>
    <div class="rounded-lg p-3 text-center" style="background:var(--card);border:1px solid var(--border);">
        <div class="text-xs mb-1" style="color:var(--dim);text-transform:uppercase;">Today Spread</div>
        <div class="text-lg font-bold" id="kpi-spread">—</div>
        <div class="text-xs mt-1" style="color:var(--dim);" id="kpi-spread-hint">sell - buy</div>
    </div>
</div>

<!-- GRID VISUALIZATION -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Grid Levels</h2>
    <div class="mb-4">
        <h3 class="text-xs font-semibold mb-2" style="color:var(--green);">BUY GRID (Bot A) — entries below anchor</h3>
        <table style="width:100%;">
            <thead><tr><th style="width:20px;"></th><th>Level</th><th>Entry &rarr; Target</th><th>Qty</th><th>Status</th><th>PnL</th><th>Cycle ID</th></tr></thead>
            <tbody id="buy-grid"></tbody>
        </table>
    </div>
    <div>
        <h3 class="text-xs font-semibold mb-2" style="color:var(--red);">SELL GRID (Bot B) — entries above anchor</h3>
        <table style="width:100%;">
            <thead><tr><th style="width:20px;"></th><th>Level</th><th>Entry &rarr; Target</th><th>Qty</th><th>Status</th><th>PnL</th><th>Cycle ID</th></tr></thead>
            <tbody id="sell-grid"></tbody>
        </table>
    </div>
</div>

<!-- PNL CHART -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Cumulative PnL</h2>
    <div style="height:200px;position:relative;"><canvas id="pnl-chart"></canvas></div>
</div>

<!-- RECENT TRANSACTIONS -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Recent Transactions</h2>
    <table>
        <thead><tr>
            <th>Group</th><th>Side</th><th>Level</th><th>Cycle</th>
            <th>Entry @</th><th>Target @</th><th>Qty</th><th>PnL</th><th>Time</th>
        </tr></thead>
        <tbody id="closed-tbody"></tbody>
    </table>
    <div class="text-center py-3" style="color:var(--dim);font-style:italic;display:none;" id="closed-empty">No completed trades yet</div>
</div>

<script>
let pnlChart = null;

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

function computeGrid(anchor, spacing, profit, levels, qty, amountPerLevel) {
    if (!anchor || anchor <= 0) return { buy: [], sell: [] };
    const buyLevels = [], sellLevels = [];
    for (let i = 0; i < levels; i++) {
        const dist = spacing * (i + 1);
        const bEntry = Math.round((anchor - dist) * 100) / 100;
        const sEntry = Math.round((anchor + dist) * 100) / 100;
        const bQty = (amountPerLevel > 0 && bEntry > 0) ? Math.max(1, Math.round(amountPerLevel / bEntry)) : qty;
        const sQty = (amountPerLevel > 0 && sEntry > 0) ? Math.max(1, Math.round(amountPerLevel / sEntry)) : qty;
        buyLevels.push({ index: i, entry: bEntry, target: Math.round((bEntry + profit) * 100) / 100, qty: bQty });
        sellLevels.push({ index: i, entry: sEntry, target: Math.round((sEntry - profit) * 100) / 100, qty: sQty });
    }
    return { buy: buyLevels, sell: sellLevels };
}

function statusBadge(status, filledSoFar, qty) {
    if (status === 'ENTRY_PENDING') return '<span class="status-badge badge-entry">ENTRY PENDING</span>';
    if (status === 'ENTRY_PARTIAL') return '<span class="status-badge badge-partial">PARTIAL ' + filledSoFar + '/' + qty + '</span>';
    if (status === 'TARGET_PENDING') return '<span class="status-badge badge-target">TARGET PENDING</span>';
    return '<span style="color:var(--dim);">Free</span>';
}

const expandedGridRows = new Set();

function toggleGridSub(rid) {
    const rows = document.querySelectorAll('.sub-' + CSS.escape(rid));
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

function renderGridLevel(lv, g, gridId) {
    const rid = gridId + '-' + lv.index;
    const isOpen = expandedGridRows.has(rid);

    let statusHTML = '<span style="color:var(--dim);">Free</span>';
    let rowClass = '';
    let priceDisplay = lv.entry.toFixed(2) + ' \u2192 ' + lv.target.toFixed(2);
    let pnlHTML = '', cycleId = '';
    let hasDetails = false;
    const qtyDisplay = lv.qty;

    if (g) {
        hasDetails = true;
        statusHTML = statusBadge(g.status, g.entry_filled_so_far || 0, g.qty || 4000);
        cycleId = '<span class="grid-id-mono">' + g.group_id + '</span>';
        const eP = g.entry_fill_price ? g.entry_fill_price.toFixed(2) : lv.entry.toFixed(2);
        priceDisplay = eP + ' \u2192 ' + lv.target.toFixed(2);

        if (g.status === 'ENTRY_PENDING') rowClass = 'grid-row-active';
        else if (g.status === 'ENTRY_PARTIAL') rowClass = 'grid-row-partial';
        else if (g.status === 'TARGET_PENDING') rowClass = 'grid-row-filled';

        if (g.realized_pnl) {
            const cls = g.realized_pnl >= 0 ? 'grid-pnl-pos' : 'grid-pnl-neg';
            pnlHTML = '<span class="' + cls + '">' + (g.realized_pnl >= 0 ? '+' : '') + g.realized_pnl.toFixed(2) + '</span>';
        }
    }

    // Main row
    const iconCls = (hasDetails && isOpen) ? 'grid-expand-icon open' : 'grid-expand-icon';
    const expandIcon = hasDetails ? '<span class="' + iconCls + '" id="icon-' + rid + '">&#9654;</span>' : '';
    let html = '<tr class="grid-main-row ' + rowClass + '" ' +
        (hasDetails ? "onclick=\\"toggleGridSub('" + rid + "')\\"" : '') + '>' +
        '<td style="width:20px;">' + expandIcon + '</td>' +
        '<td>L' + lv.index + '</td>' +
        '<td>' + priceDisplay + '</td>' +
        '<td>' + qtyDisplay + '</td>' +
        '<td>' + statusHTML + '</td>' +
        '<td>' + pnlHTML + '</td>' +
        '<td>' + cycleId + '</td></tr>';

    // Sub-rows (hidden by default, toggled on click)
    if (g) {
        const subVis = isOpen ? 'grid-sub-row sub-' : 'grid-sub-row hidden sub-';
        const cs = ' colspan="6"';

        // --- ENTRY sub-row ---
        const eSide = g.entry_side || 'BUY';
        const ePrice = g.entry_price ? g.entry_price.toFixed(2) : lv.entry.toFixed(2);
        const eQty = g.entry_filled_so_far || 0;
        const eOid = g.entry_order_id || '\u2014';
        let eDetail = '';
        if (eQty >= (g.qty || 4000)) {
            eDetail = '\u2713 filled ' + eQty + '/' + (g.qty || 4000) + (g.entry_fill_price ? ' @ ' + g.entry_fill_price.toFixed(2) : '');
        } else if (eQty > 0) {
            eDetail = 'partial ' + eQty + '/' + (g.qty || 4000) + (g.entry_fill_price ? ' @ ' + g.entry_fill_price.toFixed(2) : '');
        } else {
            eDetail = 'pending';
        }
        html += '<tr class="' + subVis + rid + '">' +
            '<td></td><td' + cs + '>' +
            '<span class="grid-sub-label entry-label">ENTRY</span> ' +
            eSide + ' ' + (g.qty || 4000) + ' @ ' + ePrice +
            '  <span style="opacity:0.6;">(' + eDetail + ')</span>' +
            '  <span class="grid-id-mono">OID:' + eOid + '</span>' +
            '</td></tr>';

        // --- TARGET sub-rows (depth-aware) ---
        const targets = g.target_orders || [];
        const depthLabelMap = {1:'TARGET', 2:'RE-ENTRY', 3:'TARGET', 4:'RE-ENTRY', 5:'FINAL'};
        const depthLabelCls = {1:'target-label', 2:'reentry-label', 3:'target-label', 4:'reentry-label', 5:'final-label'};

        targets.forEach((t, i) => {
            const depth = t.depth || 1;
            const tag = t.tag || ('T' + (i+1));
            const isClosing = (depth % 2 === 1);
            const tSide = isClosing ? (eSide === 'BUY' ? 'SELL' : 'BUY') : eSide;
            const orderPrice = isClosing ? g.target_price : g.entry_price;
            const tFilled = t.filled_qty || 0;
            const tQty = t.qty || 0;
            const tOid = t.order_id || '\u2014';
            let tDetail = '';
            if (tFilled >= tQty && tQty > 0) {
                tDetail = '\u2713 filled ' + tFilled + '/' + tQty + (t.fill_price ? ' @ ' + t.fill_price.toFixed(2) : '');
            } else if (tFilled > 0) {
                tDetail = 'partial ' + tFilled + '/' + tQty + (t.fill_price ? ' @ ' + t.fill_price.toFixed(2) : '');
            } else {
                tDetail = 'pending';
            }

            const lblText = depthLabelMap[depth] || 'TARGET';
            const lblCls = depthLabelCls[depth] || 'target-label';
            const indent = depth > 1 ? 'padding-left:' + (24 + (depth - 1) * 10) + 'px;' : '';
            const prefix = depth > 1 ? '\u2514 ' : '';

            html += '<tr class="' + subVis + rid + '">' +
                '<td></td><td' + cs + ' style="' + indent + '">' +
                prefix + '<span class="grid-sub-label ' + lblCls + '">' + lblText + '</span> ' +
                '<span style="color:var(--dim);font-size:10px;">[' + tag + ' d' + depth + ']</span> ' +
                tSide + ' ' + tQty + ' @ ' + orderPrice.toFixed(2) +
                '  <span style="opacity:0.6;">(' + tDetail + ')</span>' +
                '  <span class="grid-id-mono">OID:' + tOid + '</span>' +
                '</td></tr>';
        });
    }
    return html;
}

function updateMonitor() {
    fetch('/api/state')
        .then(r => r.json())
        .then(data => {
            const s = data.summary || {};
            const state = data.state || {};
            const running = data.running;

            // Status indicator
            const pulse = document.getElementById('status-pulse');
            const text = document.getElementById('status-text');
            if (running) {
                pulse.className = 'pulse pulse-green';
                text.textContent = 'Running (PID ' + (data.pid || '?') + ')';
            } else {
                pulse.className = 'pulse pulse-red';
                text.textContent = 'Stopped';
            }
            document.getElementById('hdr-time').textContent = new Date().toLocaleTimeString('en-IN',
                {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});

            // KPIs
            const pnlEl = document.getElementById('kpi-pnl');
            const pnl = s.total_pnl || 0;
            pnlEl.textContent = fmtPnlText(pnl);
            pnlEl.className = 'text-xl font-bold ' + (pnl >= 0 ? 'pnl-pos' : 'pnl-neg');
            const enginePnl = s.engine_pnl || 0;
            document.getElementById('kpi-engine-pnl').textContent = 'completed cycles: ' + fmtPnlText(enginePnl);
            document.getElementById('kpi-cycles').textContent = s.total_cycles || 0;
            document.getElementById('kpi-anchor').textContent = s.anchor_price ? s.anchor_price.toFixed(2) : '—';
            document.getElementById('kpi-spacing').textContent = s.current_spacing ? s.current_spacing.toFixed(4) : '—';
            const inv = s.net_inventory || 0;
            const invEl = document.getElementById('kpi-inventory');
            invEl.textContent = (inv >= 0 ? '+' : '') + inv;
            invEl.className = 'text-xl font-bold ' + (inv === 0 ? '' : inv > 0 ? 'pnl-pos' : 'pnl-neg');
            document.getElementById('kpi-reanchors').textContent =
                (s.total_reanchors || 0) + ' (B:' + (s.buy_reanchor_count || 0) + ' S:' + (s.sell_reanchor_count || 0) + ')';

            // VWAP KPIs
            const bvEl = document.getElementById('kpi-buy-vwap');
            const svEl = document.getElementById('kpi-sell-vwap');
            const spEl = document.getElementById('kpi-spread');
            if (s.buy_vwap != null) {
                bvEl.textContent = s.buy_vwap.toFixed(2);
                document.getElementById('kpi-buy-qty').textContent = s.buy_fill_qty.toLocaleString() + ' shares';
            } else {
                bvEl.textContent = '\u2014';
                document.getElementById('kpi-buy-qty').textContent = 'no fills';
            }
            if (s.sell_vwap != null) {
                svEl.textContent = s.sell_vwap.toFixed(2);
                document.getElementById('kpi-sell-qty').textContent = s.sell_fill_qty.toLocaleString() + ' shares';
            } else {
                svEl.textContent = '\u2014';
                document.getElementById('kpi-sell-qty').textContent = 'no fills';
            }
            if (s.spread != null) {
                spEl.textContent = (s.spread >= 0 ? '+' : '') + s.spread.toFixed(4);
                spEl.className = 'text-lg font-bold ' + (s.spread >= 0 ? 'pnl-pos' : 'pnl-neg');
            } else {
                spEl.textContent = '\u2014';
                spEl.className = 'text-lg font-bold';
            }

            // Grid levels
            const anchor = s.anchor_price || 0;
            const spacing = s.current_spacing || 0.01;
            const cfg = data.config || {};
            const profit = cfg.round_trip_profit || 0.01;
            const levels = cfg.levels_per_side || 10;
            const qty = cfg.qty_per_level || 4000;
            const amtPerLevel = cfg.amount_per_level || 0;
            const grid = computeGrid(anchor, spacing, profit, levels, qty, amtPerLevel);

            const og = state.open_groups || {};
            const groupByLevel = {};
            Object.values(og).forEach(g => {
                groupByLevel[g.bot + ':' + g.subset_index] = g;
            });

            // Buy grid
            document.getElementById('buy-grid').innerHTML = grid.buy.map(lv => {
                return renderGridLevel(lv, groupByLevel['A:' + lv.index], 'buy');
            }).join('');

            // Sell grid
            document.getElementById('sell-grid').innerHTML = grid.sell.map(lv => {
                return renderGridLevel(lv, groupByLevel['B:' + lv.index], 'sell');
            }).join('');

            // Closed trades
            const closed = (state.closed_groups || []).slice().sort((a,b) =>
                (b.closed_at || '').localeCompare(a.closed_at || '')).slice(0, 30);
            const closedTbody = document.getElementById('closed-tbody');
            const closedEmpty = document.getElementById('closed-empty');
            if (closed.length === 0) {
                closedTbody.innerHTML = '';
                closedEmpty.style.display = 'block';
            } else {
                closedEmpty.style.display = 'none';
                closedTbody.innerHTML = closed.map(g => {
                    const status = g.status || 'CLOSED';
                    const typeLabel = status === 'CANCELLED'
                        ? '<span class="status-badge badge-entry">CANCELLED</span>'
                        : '<span class="status-badge badge-closed">CYCLE</span>';
                    const sideBadge = g.entry_side === 'BUY'
                        ? '<span class="status-badge badge-buy">BUY</span>'
                        : '<span class="status-badge badge-sell">SELL</span>';
                    return '<tr>' +
                        '<td style="font-size:11px;color:var(--dim);">' + g.group_id + '</td>' +
                        '<td>' + sideBadge + '</td>' +
                        '<td>L' + g.subset_index + '</td>' +
                        '<td>C' + (g.cycle_number || 1) + ' ' + typeLabel + '</td>' +
                        '<td>' + (g.entry_fill_price ? g.entry_fill_price.toFixed(2) : g.entry_price.toFixed(2)) + '</td>' +
                        '<td>' + g.target_price.toFixed(2) + '</td>' +
                        '<td>' + g.qty + '</td>' +
                        '<td>' + fmtPnl(g.realized_pnl) + '</td>' +
                        '<td>' + fmtTime(g.closed_at) + '</td></tr>';
                }).join('');
            }

            // PnL chart
            const allClosed = (state.closed_groups || [])
                .filter(g => g.status === 'CLOSED')
                .sort((a,b) => (a.closed_at || '').localeCompare(b.closed_at || ''));
            if (allClosed.length > 0) {
                let cum = 0;
                const labels = [], pnlData = [];
                allClosed.forEach((g, i) => {
                    cum += g.realized_pnl || 0;
                    labels.push(i + 1);
                    pnlData.push(parseFloat(cum.toFixed(2)));
                });
                const ctx = document.getElementById('pnl-chart').getContext('2d');
                if (pnlChart) pnlChart.destroy();
                pnlChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels,
                        datasets: [{
                            label: 'Cumulative PnL',
                            data: pnlData,
                            borderColor: pnlData[pnlData.length-1] >= 0 ? '#00c853' : '#ff1744',
                            backgroundColor: (pnlData[pnlData.length-1] >= 0 ? 'rgba(0,200,83,' : 'rgba(255,23,68,') + '0.1)',
                            fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { display: true, title: { display: true, text: 'Cycle #', color: '#888' },
                                 ticks: { color: '#888', maxTicksLimit: 15 }, grid: { color: 'rgba(42,45,58,0.5)' } },
                            y: { display: true, title: { display: true, text: 'PnL', color: '#888' },
                                 ticks: { color: '#888' }, grid: { color: 'rgba(42,45,58,0.5)' } }
                        }
                    }
                });
            }
        })
        .catch(e => console.error('Monitor error:', e));
}

setInterval(updateMonitor, 3000);
setTimeout(updateMonitor, 500);
</script>
</body>
</html>'''


def _build_config_html() -> str:
    """Build the TollGate config dashboard HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TollGate Config — SPCENET</title>
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
    .field-hint { font-size: 10px; color: var(--dim); margin-top: 2px; line-height: 1.3; }
</style>
</head>
<body class="p-4 max-w-3xl mx-auto">

<!-- HEADER -->
<div class="flex justify-between items-center p-3 rounded-lg mb-4" style="background:var(--card);border:1px solid var(--border);">
    <div>
        <h1 class="text-lg font-bold">TOLLGATE CONFIG PANEL</h1>
        <span style="color:var(--dim);font-size:12px;">SPCENET market-maker configuration</span>
    </div>
    <div class="text-right" style="font-size:12px;">
        <span class="pulse pulse-red" id="status-pulse"></span>
        <span id="status-text">Loading...</span><br>
        <span style="color:var(--dim);" id="hdr-time">—</span>
    </div>
</div>

<!-- TOAST -->
<div id="toast" class="fixed top-4 right-4 px-4 py-2 rounded-lg text-sm font-semibold" style="background:var(--green);color:#000;display:none;z-index:100;">Saved</div>

<!-- BOT CONTROL -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Bot Control</h2>
    <div class="flex gap-2 items-center">
        <span id="bot-status-badge" class="status-badge badge-stopped">Stopped</span>
        <span id="bot-pid" style="color:var(--dim);font-size:11px;"></span>
        <button class="btn-green" id="btn-start" onclick="startBot()">Start Bot</button>
        <button class="btn-red" id="btn-stop" onclick="stopBot()" style="display:none;">Stop Bot</button>
    </div>
</div>

<!-- SETTINGS -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Grid Settings</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Symbol</label>
            <input id="cfg-symbol" value="SPCENET" disabled>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Base Spacing</label>
            <input id="cfg-spacing" type="number" step="0.01">
            <div class="field-hint">Distance between grid levels</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Round-Trip Profit</label>
            <input id="cfg-profit" type="number" step="0.01">
            <div class="field-hint">Profit target per cycle</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Levels Per Side</label>
            <input id="cfg-levels" type="number">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Qty Per Level</label>
            <input id="cfg-qty" type="number">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Amount Per Level</label>
            <input id="cfg-amount" type="number" step="100">
            <div class="field-hint">If > 0, overrides Qty. qty = round(amount/price)</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Disclosed Pct</label>
            <input id="cfg-disclosed" type="number" step="5" min="0" max="100">
            <div class="field-hint">0 = show full qty, e.g. 25 = show 25%</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Max Reanchors</label>
            <input id="cfg-max-reanchors" type="number">
            <div class="field-hint">Stop bot after N reanchors</div>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Product</label>
            <select id="cfg-product">
                <option value="CNC">CNC</option>
                <option value="NRML">NRML</option>
                <option value="MIS">MIS</option>
            </select>
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Poll Interval (s)</label>
            <input id="cfg-poll" type="number" step="0.5">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">Anchor Price</label>
            <input id="cfg-anchor" type="number" step="0.01">
            <div class="field-hint">0 if auto-anchor</div>
        </div>
    </div>
    <div class="mt-3">
        <label class="flex items-center gap-2 text-xs cursor-pointer" style="color:var(--text);">
            <input type="checkbox" id="cfg-auto-anchor" style="width:auto;"> Auto Anchor (use LTP on start)
        </label>
    </div>
</div>

<!-- CREDENTIALS -->
<div class="rounded-lg p-4 mb-4" style="background:var(--card);border:1px solid var(--border);">
    <h2 class="text-sm font-semibold mb-3" style="color:var(--dim);text-transform:uppercase;letter-spacing:0.5px;">Credentials</h2>
    <div class="grid grid-cols-2 gap-3">
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Interactive Key</label>
            <input id="cfg-key" style="font-size:10px;">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Interactive Secret</label>
            <input id="cfg-secret" type="password" style="font-size:10px;">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Market Data Key</label>
            <input id="cfg-md-key" style="font-size:10px;">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Market Data Secret</label>
            <input id="cfg-md-secret" type="password" style="font-size:10px;">
        </div>
        <div>
            <label class="block text-xs mb-1" style="color:var(--dim);">XTS Root URL</label>
            <input id="cfg-xts-root" style="font-size:10px;">
        </div>
    </div>
</div>

<!-- ACTION BUTTONS -->
<div class="flex gap-2 mb-4">
    <button class="btn-green" onclick="saveConfig()">Save Config</button>
    <button class="btn-dim" onclick="loadConfig()">Reload</button>
</div>

<script>
function showToast(msg, color) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.style.background = color || 'var(--green)';
    t.style.display = 'block';
    setTimeout(() => { t.style.display = 'none'; }, 2000);
}

function loadConfig() {
    fetch('/api/config')
        .then(r => r.json())
        .then(cfg => {
            document.getElementById('cfg-spacing').value = cfg.base_spacing || 0.01;
            document.getElementById('cfg-profit').value = cfg.round_trip_profit || 0.01;
            document.getElementById('cfg-levels').value = cfg.levels_per_side || 10;
            document.getElementById('cfg-qty').value = cfg.qty_per_level || 4000;
            document.getElementById('cfg-amount').value = cfg.amount_per_level || 0;
            document.getElementById('cfg-disclosed').value = cfg.disclosed_pct || 0;
            document.getElementById('cfg-max-reanchors').value = cfg.max_reanchors || 100;
            document.getElementById('cfg-product').value = cfg.product || 'NRML';
            document.getElementById('cfg-poll').value = cfg.poll_interval || 2.0;
            document.getElementById('cfg-anchor').value = cfg.anchor_price || 0;
            document.getElementById('cfg-auto-anchor').checked = cfg.auto_anchor !== false;
            document.getElementById('cfg-key').value = cfg.interactive_key || '';
            document.getElementById('cfg-secret').value = cfg.interactive_secret || '';
            document.getElementById('cfg-md-key').value = cfg.marketdata_key || '';
            document.getElementById('cfg-md-secret').value = cfg.marketdata_secret || '';
            document.getElementById('cfg-xts-root').value = cfg.xts_root || '';
        })
        .catch(e => console.error('Load config error:', e));
}

function saveConfig() {
    const cfg = {
        symbol: 'SPCENET',
        base_spacing: parseFloat(document.getElementById('cfg-spacing').value),
        round_trip_profit: parseFloat(document.getElementById('cfg-profit').value),
        levels_per_side: parseInt(document.getElementById('cfg-levels').value),
        qty_per_level: parseInt(document.getElementById('cfg-qty').value),
        amount_per_level: parseFloat(document.getElementById('cfg-amount').value),
        disclosed_pct: parseFloat(document.getElementById('cfg-disclosed').value),
        max_reanchors: parseInt(document.getElementById('cfg-max-reanchors').value),
        product: document.getElementById('cfg-product').value,
        poll_interval: parseFloat(document.getElementById('cfg-poll').value),
        anchor_price: parseFloat(document.getElementById('cfg-anchor').value),
        auto_anchor: document.getElementById('cfg-auto-anchor').checked,
        interactive_key: document.getElementById('cfg-key').value.trim(),
        interactive_secret: document.getElementById('cfg-secret').value.trim(),
        marketdata_key: document.getElementById('cfg-md-key').value.trim(),
        marketdata_secret: document.getElementById('cfg-md-secret').value.trim(),
        xts_root: document.getElementById('cfg-xts-root').value.trim(),
    };
    fetch('/api/config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(cfg),
    })
    .then(r => r.json())
    .then(r => {
        if (r.status === 'ok') showToast('Config saved');
        else showToast('Save failed: ' + (r.error || ''), 'var(--red)');
    })
    .catch(e => showToast('Save error', 'var(--red)'));
}

function startBot() {
    fetch('/api/bot/start', {method: 'POST'})
        .then(r => r.json())
        .then(r => {
            if (r.status === 'started') showToast('Bot started');
            else showToast(r.error || 'Failed', 'var(--red)');
            updateProcesses();
        })
        .catch(e => showToast('Start error', 'var(--red)'));
}

function stopBot() {
    fetch('/api/bot/stop', {method: 'POST'})
        .then(r => r.json())
        .then(r => {
            if (r.status === 'stopped') showToast('Bot stopped');
            else showToast(r.error || 'Not running', 'var(--orange)');
            updateProcesses();
        })
        .catch(e => showToast('Stop error', 'var(--red)'));
}

function updateProcesses() {
    fetch('/api/processes')
        .then(r => r.json())
        .then(procs => {
            const info = procs.SPCENET || {};
            const running = info.running || false;
            const pid = info.pid;

            const pulse = document.getElementById('status-pulse');
            const text = document.getElementById('status-text');
            const badge = document.getElementById('bot-status-badge');
            const pidEl = document.getElementById('bot-pid');
            const startBtn = document.getElementById('btn-start');
            const stopBtn = document.getElementById('btn-stop');

            if (running) {
                pulse.className = 'pulse pulse-green';
                text.textContent = 'Running';
                badge.className = 'status-badge badge-running';
                badge.textContent = 'Running';
                pidEl.textContent = pid ? 'PID ' + pid : '';
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
            } else {
                pulse.className = 'pulse pulse-red';
                text.textContent = 'Stopped';
                badge.className = 'status-badge badge-stopped';
                badge.textContent = 'Stopped';
                pidEl.textContent = '';
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
            }
            document.getElementById('hdr-time').textContent = new Date().toLocaleTimeString('en-IN',
                {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
        })
        .catch(e => {});
}

loadConfig();
updateProcesses();
setInterval(updateProcesses, 5000);
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='TollGate Dashboard')
    parser.add_argument('--port', type=int, default=7788, help='Dashboard port')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    parser.add_argument('--mode', default='monitor', choices=['monitor', 'config'],
                        help='Dashboard mode')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    if not os.path.exists(CONFIG_FILE):
        _save_config(_DEFAULT_CONFIG)

    app = create_app(mode=args.mode)
    logger.info("Starting TollGate Dashboard (%s) on %s:%d", args.mode, args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
