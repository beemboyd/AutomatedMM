"""
AMM Dashboard — Monitor (7797) + Config/Admin (7796) web UI.

Features:
- Monitor mode (--mode monitor, port 7797): Ratio charts, positions, PnL
- Config mode (--mode config, port 7796): Edit config, start/stop bot

Usage:
    python -m TG.AMM.run --dashboard --mode monitor --port 7797
    python -m TG.AMM.run --dashboard --mode config --port 7796
"""

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
CONFIG_FILE = os.path.join(STATE_DIR, 'amm_config.json')
PID_FILE = os.path.join(STATE_DIR, '.bot_pids.json')
STATE_FILE = os.path.join(STATE_DIR, 'amm_state.json')

_DEFAULT_CONFIG = {
    "pairs": [
        {"numerator_ticker": "TATAGOLD", "denominator_ticker": "SPCENET",
         "entry_sd": 1.0, "numerator_trade_pct": 100, "denominator_trade_pct": 100,
         "enabled": True},
        {"numerator_ticker": "YESBANK", "denominator_ticker": "SPCENET",
         "entry_sd": 1.0, "numerator_trade_pct": 100, "denominator_trade_pct": 100,
         "enabled": True},
    ],
    "base_qty": 10000,
    "rolling_window": 30,
    "sample_interval": 60,
    "warmup_samples": 30,
    "max_positions_per_pair": 3,
    "mean_reversion_tolerance": 0.002,
    "exchange": "NSE",
    "product": "CNC",
    "poll_interval": 2.0,
    "slippage": 0.05,
    "interactive_key": "8971817fbc4b2ee3607278",
    "interactive_secret": "Spit105$uM",
    "marketdata_key": "562d110e40e3b820c95672",
    "marketdata_secret": "Stlf310$q$",
    "xts_root": "https://xts.myfindoc.com",
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
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to load state: %s", e)
        return {}


def _is_bot_running() -> bool:
    pids = _load_bot_pids()
    pid = pids.get('AMM')
    if pid is None:
        return False
    if _pid_alive(pid):
        return True
    pids.pop('AMM', None)
    _save_bot_pids(pids)
    return False


def _get_bot_pid() -> Optional[int]:
    pids = _load_bot_pids()
    pid = pids.get('AMM')
    if pid and _pid_alive(pid):
        return pid
    return None


def _start_bot(config: dict) -> bool:
    if _is_bot_running():
        return False

    cmd = [
        sys.executable, '-m', 'TG.AMM.run',
        '--config-file', CONFIG_FILE,
        '--base-qty', str(config.get('base_qty', 10000)),
        '--rolling-window', str(config.get('rolling_window', 30)),
        '--sample-interval', str(config.get('sample_interval', 60)),
        '--product', config.get('product', 'CNC'),
        '--max-positions', str(config.get('max_positions_per_pair', 3)),
        '--poll-interval', str(config.get('poll_interval', 2.0)),
        '--slippage', str(config.get('slippage', 0.05)),
        '--warmup-samples', str(config.get('warmup_samples', 30)),
        '--mean-reversion-tolerance', str(config.get('mean_reversion_tolerance', 0.002)),
        '--interactive-key', config.get('interactive_key', ''),
        '--interactive-secret', config.get('interactive_secret', ''),
        '--marketdata-key', config.get('marketdata_key', ''),
        '--marketdata-secret', config.get('marketdata_secret', ''),
        '--xts-root', config.get('xts_root', 'https://xts.myfindoc.com'),
    ]

    # Save config to file so engine can load pair configs
    _save_config(config)

    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'amm_engine.log')

    with open(log_file, 'a') as lf:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT,
            stdout=lf, stderr=subprocess.STDOUT,
        )

    pids = _load_bot_pids()
    pids['AMM'] = proc.pid
    _save_bot_pids(pids)
    logger.info("Started AMM bot: PID=%d", proc.pid)
    return True


def _stop_bot() -> bool:
    pids = _load_bot_pids()
    pid = pids.get('AMM')
    if pid is None:
        return False
    if not _pid_alive(pid):
        pids.pop('AMM', None)
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
        logger.info("Stopped AMM bot (PID=%d)", pid)
    except ProcessLookupError:
        pass
    except Exception as e:
        logger.error("Error stopping AMM bot (PID=%d): %s", pid, e)

    pids.pop('AMM', None)
    _save_bot_pids(pids)
    return True


def _compute_summary(state: dict, config: dict) -> dict:
    """Compute dashboard summary from raw state."""
    if not state:
        return {}

    open_positions = state.get('open_positions', {})
    closed_positions = state.get('closed_positions', [])

    entering = sum(1 for p in open_positions.values() if p.get('status') == 'ENTERING')
    open_ct = sum(1 for p in open_positions.values() if p.get('status') == 'OPEN')
    exiting = sum(1 for p in open_positions.values() if p.get('status') == 'EXITING')

    wins = sum(1 for p in closed_positions if p.get('realized_pnl', 0) > 0)
    win_rate = (wins / len(closed_positions) * 100) if closed_positions else 0.0

    # Warmup status per pair
    pairs = config.get('pairs', [])
    warmup_samples = config.get('warmup_samples', 30)
    ratio_series = state.get('ratio_series', {})
    warmup_status = {}
    for i in range(len(pairs)):
        series = ratio_series.get(str(i), [])
        warmup_status[str(i)] = {
            'samples': len(series),
            'needed': warmup_samples,
            'ready': len(series) >= warmup_samples,
        }

    return {
        'total_pnl': round(state.get('total_pnl', 0), 2),
        'total_trades': state.get('total_trades', 0),
        'open_count': len(open_positions),
        'entering': entering,
        'open': open_ct,
        'exiting': exiting,
        'win_rate': round(win_rate, 1),
        'warmup_status': warmup_status,
        'last_updated': state.get('last_updated', ''),
    }


def _compute_ratios(state: dict, config: dict) -> dict:
    """Compute ratio summary for each pair."""
    import statistics as stats_mod
    ratios = {}
    ratio_series = state.get('ratio_series', {})
    rolling_window = config.get('rolling_window', 30)

    for pair_idx_str, samples in ratio_series.items():
        if not samples:
            ratios[pair_idx_str] = {'samples': [], 'mean': None, 'sd': None, 'z_score': None}
            continue

        # Last 60 samples for chart display
        display_samples = samples[-60:]
        ratios_list = [s['ratio'] for s in samples]

        mean = None
        sd = None
        z_score = None

        if len(ratios_list) >= rolling_window:
            recent = ratios_list[-rolling_window:]
            mean = round(stats_mod.mean(recent), 8)
            sd = round(stats_mod.stdev(recent), 8) if len(recent) > 1 else 0.0
            if sd > 0:
                z_score = round((ratios_list[-1] - mean) / sd, 4)

        ratios[pair_idx_str] = {
            'samples': display_samples,
            'mean': mean,
            'sd': sd,
            'z_score': z_score,
        }

    return ratios


def create_app(mode: str = 'monitor') -> Flask:
    """Create Flask app. mode='monitor' for 7797, mode='config' for 7796."""
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
            'ratios': _compute_ratios(state, config),
            'summary': _compute_summary(state, config),
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
            'AMM': {
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


# ============================================================
# Monitor Dashboard HTML (port 7797)
# ============================================================

def _build_monitor_html() -> str:
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AMM Stat-Arb Monitor</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    :root {
        --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a; --text: #e0e0e0;
        --dim: #888; --green: #00c853; --red: #ff1744; --blue: #448aff;
        --orange: #ff9100; --purple: #b388ff; --cyan: #18ffff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        background: var(--bg); color: var(--text); font-size: 13px;
    }
    .pulse { display:inline-block; width:8px; height:8px; border-radius:50%;
             margin-right:6px; animation: pulse 2s ease-in-out infinite; }
    .pulse-green { background: var(--green); }
    .pulse-red { background: var(--red); }
    .pulse-orange { background: var(--orange); }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }
    .pnl-pos { color: var(--green); font-weight: 600; }
    .pnl-neg { color: var(--red); font-weight: 600; }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 16px; }
    .badge { display:inline-block; padding:2px 6px; border-radius:4px;
             font-size:10px; font-weight:600; }
    .badge-running { background:rgba(0,200,83,0.15); color:var(--green); }
    .badge-stopped { background:rgba(255,23,68,0.15); color:var(--red); }
    .badge-warmup { background:rgba(255,145,0,0.15); color:var(--orange); }
    .badge-long { background:rgba(0,200,83,0.10); color:var(--green); }
    .badge-short { background:rgba(255,23,68,0.10); color:var(--red); }
    table { width:100%; border-collapse:collapse; font-size:12px; }
    th { text-align:left; padding:6px 8px; border-bottom:1px solid var(--border);
         color:var(--dim); font-weight:500; font-size:11px; text-transform:uppercase; }
    td { padding:6px 8px; border-bottom:1px solid rgba(42,45,58,0.5); }
    .kpi-val { font-size:24px; font-weight:700; }
    .kpi-label { font-size:11px; color:var(--dim); text-transform:uppercase; }
</style>
</head>
<body>
<div style="max-width:1400px;margin:0 auto;padding:16px;">

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
    <div>
        <h1 style="font-size:18px;font-weight:700;">AMM Stat-Arb Monitor</h1>
        <span style="color:var(--dim);font-size:11px;">Ratio Mean-Reversion Market Maker</span>
    </div>
    <div id="header-status" style="text-align:right;">
        <span class="badge badge-stopped">LOADING</span>
        <div style="color:var(--dim);font-size:10px;margin-top:4px;" id="header-time"></div>
    </div>
</div>

<!-- KPI Cards -->
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px;">
    <div class="card"><div class="kpi-label">Total PnL</div><div class="kpi-val" id="kpi-pnl">--</div></div>
    <div class="card"><div class="kpi-label">Open Positions</div><div class="kpi-val" id="kpi-open">--</div></div>
    <div class="card"><div class="kpi-label">Total Trades</div><div class="kpi-val" id="kpi-trades">--</div></div>
    <div class="card"><div class="kpi-label">Win Rate</div><div class="kpi-val" id="kpi-winrate">--</div></div>
    <div class="card"><div class="kpi-label">Warmup</div><div class="kpi-val" id="kpi-warmup">--</div></div>
</div>

<!-- Ratio Charts -->
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px;">
    <div class="card">
        <div style="font-size:12px;font-weight:600;margin-bottom:8px;" id="chart0-label">Pair 0</div>
        <canvas id="ratioChart0" height="200"></canvas>
    </div>
    <div class="card">
        <div style="font-size:12px;font-weight:600;margin-bottom:8px;" id="chart1-label">Pair 1</div>
        <canvas id="ratioChart1" height="200"></canvas>
    </div>
</div>

<!-- Open Positions -->
<div class="card" style="margin-bottom:16px;">
    <div style="font-size:14px;font-weight:600;margin-bottom:8px;">Open Positions</div>
    <table>
        <thead><tr>
            <th>ID</th><th>Pair</th><th>Direction</th><th>Status</th>
            <th>Entry R</th><th>Entry Mean</th><th>Entry SD</th>
            <th>Num Qty</th><th>Den Qty</th><th>Entry Time</th>
        </tr></thead>
        <tbody id="open-positions-body"></tbody>
    </table>
    <div id="no-positions" style="color:var(--dim);text-align:center;padding:20px;display:none;">No open positions</div>
</div>

<!-- Recent Trades -->
<div class="card">
    <div style="font-size:14px;font-weight:600;margin-bottom:8px;">Recent Trades</div>
    <table>
        <thead><tr>
            <th>ID</th><th>Pair</th><th>Direction</th>
            <th>Entry R</th><th>PnL</th>
            <th>Num Fill</th><th>Den Fill</th><th>Closed At</th>
        </tr></thead>
        <tbody id="closed-positions-body"></tbody>
    </table>
    <div id="no-trades" style="color:var(--dim);text-align:center;padding:20px;display:none;">No trades yet</div>
</div>

</div>

<script>
let charts = {};

function initChart(canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Ratio', data: [], borderColor: '#448aff', borderWidth: 1.5,
                  pointRadius: 0, fill: false, tension: 0.1 },
                { label: 'Mean', data: [], borderColor: '#ff9100', borderWidth: 1,
                  borderDash: [4,4], pointRadius: 0, fill: false },
                { label: '+SD', data: [], borderColor: 'rgba(255,23,68,0.4)', borderWidth: 1,
                  borderDash: [2,2], pointRadius: 0, fill: false },
                { label: '-SD', data: [], borderColor: 'rgba(0,200,83,0.4)', borderWidth: 1,
                  borderDash: [2,2], pointRadius: 0, fill: false },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { display: true, labels: { color: '#888', font: { size: 10 } } } },
            scales: {
                x: { display: true, ticks: { color: '#555', font: { size: 9 }, maxTicksLimit: 8 },
                     grid: { color: 'rgba(42,45,58,0.5)' } },
                y: { ticks: { color: '#888', font: { size: 10 } },
                     grid: { color: 'rgba(42,45,58,0.5)' } }
            }
        }
    });
}

function updateChart(chart, ratioData) {
    if (!ratioData || !ratioData.samples || ratioData.samples.length === 0) return;
    const labels = ratioData.samples.map(s => {
        const t = s.timestamp || '';
        return t.substring(11, 16);
    });
    const ratios = ratioData.samples.map(s => s.ratio);
    const mean = ratioData.mean;
    const sd = ratioData.sd;

    chart.data.labels = labels;
    chart.data.datasets[0].data = ratios;
    chart.data.datasets[1].data = mean !== null ? labels.map(() => mean) : [];
    chart.data.datasets[2].data = (mean !== null && sd !== null) ? labels.map(() => mean + sd) : [];
    chart.data.datasets[3].data = (mean !== null && sd !== null) ? labels.map(() => mean - sd) : [];
    chart.update('none');
}

function pnlClass(val) { return val >= 0 ? 'pnl-pos' : 'pnl-neg'; }
function pnlStr(val) { return (val >= 0 ? '+' : '') + val.toFixed(2); }

function refresh() {
    fetch('/api/state')
        .then(r => r.json())
        .then(data => {
            const { state, ratios, summary, running, pid, config } = data;

            // Header
            const hs = document.getElementById('header-status');
            if (running) {
                hs.innerHTML = '<span class="pulse pulse-green"></span><span class="badge badge-running">RUNNING</span> PID ' + pid;
            } else {
                const warmupReady = summary.warmup_status && Object.values(summary.warmup_status).every(w => w.ready);
                if (!warmupReady && Object.keys(summary.warmup_status || {}).length > 0) {
                    hs.innerHTML = '<span class="pulse pulse-orange"></span><span class="badge badge-warmup">WARMUP</span>';
                } else {
                    hs.innerHTML = '<span class="pulse pulse-red"></span><span class="badge badge-stopped">STOPPED</span>';
                }
            }
            document.getElementById('header-time').textContent = summary.last_updated ? summary.last_updated.substring(0,19) : '';

            // KPIs
            const pnlEl = document.getElementById('kpi-pnl');
            pnlEl.textContent = pnlStr(summary.total_pnl || 0);
            pnlEl.className = 'kpi-val ' + pnlClass(summary.total_pnl || 0);
            document.getElementById('kpi-open').textContent = summary.open_count || 0;
            document.getElementById('kpi-trades').textContent = summary.total_trades || 0;
            document.getElementById('kpi-winrate').textContent = (summary.win_rate || 0) + '%';

            // Warmup
            const ws = summary.warmup_status || {};
            const warmupParts = Object.entries(ws).map(([k, v]) => 'P' + k + ':' + v.samples + '/' + v.needed);
            document.getElementById('kpi-warmup').textContent = warmupParts.join(' ') || '--';

            // Chart labels
            const pairs = config.pairs || [];
            if (pairs[0]) document.getElementById('chart0-label').textContent =
                'R0: ' + pairs[0].numerator_ticker + ' / ' + pairs[0].denominator_ticker +
                (ratios['0'] && ratios['0'].z_score !== null ? '  z=' + ratios['0'].z_score.toFixed(2) : '');
            if (pairs[1]) document.getElementById('chart1-label').textContent =
                'R1: ' + pairs[1].numerator_ticker + ' / ' + pairs[1].denominator_ticker +
                (ratios['1'] && ratios['1'].z_score !== null ? '  z=' + ratios['1'].z_score.toFixed(2) : '');

            // Charts
            if (!charts['0']) charts['0'] = initChart('ratioChart0');
            if (!charts['1']) charts['1'] = initChart('ratioChart1');
            if (ratios['0']) updateChart(charts['0'], ratios['0']);
            if (ratios['1']) updateChart(charts['1'], ratios['1']);

            // Open positions table
            const openBody = document.getElementById('open-positions-body');
            const openPos = Object.values(state.open_positions || {});
            if (openPos.length === 0) {
                openBody.innerHTML = '';
                document.getElementById('no-positions').style.display = 'block';
            } else {
                document.getElementById('no-positions').style.display = 'none';
                openBody.innerHTML = openPos.map(p => {
                    const pair = pairs[p.pair_index] || {};
                    const dirBadge = p.direction === 'LONG_NUM'
                        ? '<span class="badge badge-long">LONG NUM</span>'
                        : '<span class="badge badge-short">SHORT NUM</span>';
                    return '<tr>' +
                        '<td>' + p.position_id + '</td>' +
                        '<td>' + (pair.numerator_ticker||'?') + '/' + (pair.denominator_ticker||'?') + '</td>' +
                        '<td>' + dirBadge + '</td>' +
                        '<td>' + p.status + '</td>' +
                        '<td>' + (p.entry_ratio||0).toFixed(6) + '</td>' +
                        '<td>' + (p.entry_mean||0).toFixed(6) + '</td>' +
                        '<td>' + (p.entry_sd||0).toFixed(6) + '</td>' +
                        '<td>' + p.num_qty + '</td>' +
                        '<td>' + p.den_qty + '</td>' +
                        '<td>' + (p.entry_time||'').substring(11,19) + '</td>' +
                        '</tr>';
                }).join('');
            }

            // Closed positions table
            const closedBody = document.getElementById('closed-positions-body');
            const closedPos = (state.closed_positions || []).slice(-20).reverse();
            if (closedPos.length === 0) {
                closedBody.innerHTML = '';
                document.getElementById('no-trades').style.display = 'block';
            } else {
                document.getElementById('no-trades').style.display = 'none';
                closedBody.innerHTML = closedPos.map(p => {
                    const pair = pairs[p.pair_index] || {};
                    const pnl = p.realized_pnl || 0;
                    return '<tr>' +
                        '<td>' + p.position_id + '</td>' +
                        '<td>' + (pair.numerator_ticker||'?') + '/' + (pair.denominator_ticker||'?') + '</td>' +
                        '<td>' + p.direction + '</td>' +
                        '<td>' + (p.entry_ratio||0).toFixed(6) + '</td>' +
                        '<td class="' + pnlClass(pnl) + '">' + pnlStr(pnl) + '</td>' +
                        '<td>' + (p.num_entry_fill_price||0).toFixed(2) + ' / ' + (p.num_exit_fill_price||0).toFixed(2) + '</td>' +
                        '<td>' + (p.den_entry_fill_price||0).toFixed(2) + ' / ' + (p.den_exit_fill_price||0).toFixed(2) + '</td>' +
                        '<td>' + (p.closed_at||'').substring(11,19) + '</td>' +
                        '</tr>';
                }).join('');
            }
        })
        .catch(err => console.error('Refresh error:', err));
}

refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>'''


# ============================================================
# Config/Admin Dashboard HTML (port 7796)
# ============================================================

def _build_config_html() -> str:
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AMM Config / Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    :root {
        --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a; --text: #e0e0e0;
        --dim: #888; --green: #00c853; --red: #ff1744; --blue: #448aff;
        --orange: #ff9100;
    }
    * { margin:0; padding:0; box-sizing:border-box; }
    body {
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        background: var(--bg); color: var(--text); font-size: 13px;
    }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .badge { display:inline-block; padding:2px 8px; border-radius:4px;
             font-size:11px; font-weight:600; }
    .badge-running { background:rgba(0,200,83,0.15); color:var(--green); }
    .badge-stopped { background:rgba(255,23,68,0.15); color:var(--red); }
    label { display:block; font-size:11px; color:var(--dim); margin-bottom:4px;
            text-transform:uppercase; }
    input, select {
        width:100%; padding:8px; background:#0f1117; border:1px solid var(--border);
        border-radius:4px; color:var(--text); font-family:inherit; font-size:12px;
        margin-bottom:12px;
    }
    input:focus, select:focus { outline:none; border-color:var(--blue); }
    button {
        padding:8px 16px; border-radius:6px; border:none; font-family:inherit;
        font-size:12px; font-weight:600; cursor:pointer; margin-right:8px;
    }
    .btn-start { background:var(--green); color:#000; }
    .btn-stop { background:var(--red); color:#fff; }
    .btn-save { background:var(--blue); color:#fff; }
    .btn-reload { background:var(--orange); color:#000; }
    .btn-start:hover { opacity:0.9; } .btn-stop:hover { opacity:0.9; }
    .btn-save:hover { opacity:0.9; } .btn-reload:hover { opacity:0.9; }
    .pair-card { border-left: 3px solid var(--blue); padding-left: 12px; }
    .toggle { position:relative; width:40px; height:20px; display:inline-block; }
    .toggle input { opacity:0; width:0; height:0; }
    .toggle .slider { position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0;
        background:#555; border-radius:20px; transition:0.3s; }
    .toggle .slider:before { content:""; position:absolute; height:16px; width:16px;
        left:2px; bottom:2px; background:#fff; border-radius:50%; transition:0.3s; }
    .toggle input:checked + .slider { background:var(--green); }
    .toggle input:checked + .slider:before { transform:translateX(20px); }
    .status-msg { padding:8px; border-radius:4px; margin-top:8px; font-size:11px; display:none; }
    .status-ok { background:rgba(0,200,83,0.1); color:var(--green); display:block; }
    .status-err { background:rgba(255,23,68,0.1); color:var(--red); display:block; }
</style>
</head>
<body>
<div style="max-width:900px;margin:0 auto;padding:16px;">

<!-- Header -->
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
    <div>
        <h1 style="font-size:18px;font-weight:700;">AMM Config / Admin</h1>
        <span style="color:var(--dim);font-size:11px;">Stat-Arb Bot Configuration</span>
    </div>
    <div id="bot-status"><span class="badge badge-stopped">CHECKING...</span></div>
</div>

<!-- Bot Control -->
<div class="card">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Bot Control</div>
    <button class="btn-start" onclick="startBot()">Start Bot</button>
    <button class="btn-stop" onclick="stopBot()">Stop Bot</button>
    <div id="control-msg" class="status-msg"></div>
</div>

<!-- Global Settings -->
<div class="card">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;">Global Settings</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
        <div><label>Base Qty</label><input type="number" id="base_qty"></div>
        <div><label>Rolling Window</label><input type="number" id="rolling_window"></div>
        <div><label>Sample Interval (s)</label><input type="number" id="sample_interval"></div>
        <div><label>Warmup Samples</label><input type="number" id="warmup_samples"></div>
        <div><label>Max Positions/Pair</label><input type="number" id="max_positions_per_pair"></div>
        <div><label>Mean Rev Tolerance</label><input type="number" step="0.001" id="mean_reversion_tolerance"></div>
        <div><label>Product</label>
            <select id="product"><option>CNC</option><option>MIS</option><option>NRML</option></select>
        </div>
        <div><label>Poll Interval (s)</label><input type="number" step="0.1" id="poll_interval"></div>
        <div><label>Slippage</label><input type="number" step="0.01" id="slippage"></div>
    </div>
</div>

<!-- Pair Configs -->
<div id="pair-configs"></div>

<!-- Credentials (read-only) -->
<div class="card">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px;">XTS Credentials (01MU07)</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div><label>Interactive Key</label><input type="text" id="interactive_key" readonly style="opacity:0.6;"></div>
        <div><label>Interactive Secret</label><input type="text" id="interactive_secret" readonly style="opacity:0.6;"></div>
        <div><label>Market Data Key</label><input type="text" id="marketdata_key" readonly style="opacity:0.6;"></div>
        <div><label>Market Data Secret</label><input type="text" id="marketdata_secret" readonly style="opacity:0.6;"></div>
    </div>
</div>

<!-- Save/Reload -->
<div style="margin-top:16px;">
    <button class="btn-save" onclick="saveConfig()">Save Config</button>
    <button class="btn-reload" onclick="loadConfig()">Reload</button>
    <div id="save-msg" class="status-msg"></div>
</div>

</div>

<script>
let currentConfig = {};

function loadConfig() {
    fetch('/api/config').then(r => r.json()).then(cfg => {
        currentConfig = cfg;
        document.getElementById('base_qty').value = cfg.base_qty || 10000;
        document.getElementById('rolling_window').value = cfg.rolling_window || 30;
        document.getElementById('sample_interval').value = cfg.sample_interval || 60;
        document.getElementById('warmup_samples').value = cfg.warmup_samples || 30;
        document.getElementById('max_positions_per_pair').value = cfg.max_positions_per_pair || 3;
        document.getElementById('mean_reversion_tolerance').value = cfg.mean_reversion_tolerance || 0.002;
        document.getElementById('product').value = cfg.product || 'CNC';
        document.getElementById('poll_interval').value = cfg.poll_interval || 2.0;
        document.getElementById('slippage').value = cfg.slippage || 0.05;
        document.getElementById('interactive_key').value = cfg.interactive_key || '';
        document.getElementById('interactive_secret').value = cfg.interactive_secret || '';
        document.getElementById('marketdata_key').value = cfg.marketdata_key || '';
        document.getElementById('marketdata_secret').value = cfg.marketdata_secret || '';
        renderPairs(cfg.pairs || []);
    });
}

function renderPairs(pairs) {
    const container = document.getElementById('pair-configs');
    container.innerHTML = '';
    pairs.forEach((pair, i) => {
        container.innerHTML += `
        <div class="card pair-card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <div style="font-size:14px;font-weight:600;">Pair ${i}: ${pair.numerator_ticker} / ${pair.denominator_ticker}</div>
                <label class="toggle">
                    <input type="checkbox" id="pair_enabled_${i}" ${pair.enabled ? 'checked' : ''}>
                    <span class="slider"></span>
                </label>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;">
                <div><label>Numerator Ticker</label><input type="text" id="pair_num_${i}" value="${pair.numerator_ticker}"></div>
                <div><label>Denominator Ticker</label><input type="text" id="pair_den_${i}" value="${pair.denominator_ticker}"></div>
                <div><label>Entry SD</label><input type="number" step="0.1" id="pair_sd_${i}" value="${pair.entry_sd}"></div>
                <div><label>Numerator Trade %</label><input type="number" id="pair_numpct_${i}" value="${pair.numerator_trade_pct}"></div>
                <div><label>Denominator Trade %</label><input type="number" id="pair_denpct_${i}" value="${pair.denominator_trade_pct}"></div>
            </div>
        </div>`;
    });
}

function gatherConfig() {
    const cfg = Object.assign({}, currentConfig);
    cfg.base_qty = parseInt(document.getElementById('base_qty').value) || 10000;
    cfg.rolling_window = parseInt(document.getElementById('rolling_window').value) || 30;
    cfg.sample_interval = parseInt(document.getElementById('sample_interval').value) || 60;
    cfg.warmup_samples = parseInt(document.getElementById('warmup_samples').value) || 30;
    cfg.max_positions_per_pair = parseInt(document.getElementById('max_positions_per_pair').value) || 3;
    cfg.mean_reversion_tolerance = parseFloat(document.getElementById('mean_reversion_tolerance').value) || 0.002;
    cfg.product = document.getElementById('product').value;
    cfg.poll_interval = parseFloat(document.getElementById('poll_interval').value) || 2.0;
    cfg.slippage = parseFloat(document.getElementById('slippage').value) || 0.05;

    const pairs = currentConfig.pairs || [];
    cfg.pairs = pairs.map((p, i) => ({
        numerator_ticker: (document.getElementById('pair_num_'+i) || {}).value || p.numerator_ticker,
        denominator_ticker: (document.getElementById('pair_den_'+i) || {}).value || p.denominator_ticker,
        entry_sd: parseFloat((document.getElementById('pair_sd_'+i) || {}).value) || 1.0,
        numerator_trade_pct: parseFloat((document.getElementById('pair_numpct_'+i) || {}).value) || 100,
        denominator_trade_pct: parseFloat((document.getElementById('pair_denpct_'+i) || {}).value) || 100,
        enabled: (document.getElementById('pair_enabled_'+i) || {}).checked !== false,
    }));
    return cfg;
}

function saveConfig() {
    const cfg = gatherConfig();
    fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(cfg)
    }).then(r => r.json()).then(res => {
        const msg = document.getElementById('save-msg');
        if (res.status === 'ok') {
            msg.className = 'status-msg status-ok';
            msg.textContent = 'Config saved successfully';
        } else {
            msg.className = 'status-msg status-err';
            msg.textContent = 'Error: ' + (res.error || 'Unknown');
        }
        setTimeout(() => { msg.style.display = 'none'; }, 3000);
    });
}

function startBot() {
    // Save config first, then start
    const cfg = gatherConfig();
    fetch('/api/config', { method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(cfg)
    }).then(() => {
        fetch('/api/bot/start', { method:'POST' }).then(r => r.json()).then(res => {
            const msg = document.getElementById('control-msg');
            if (res.status === 'started') {
                msg.className = 'status-msg status-ok';
                msg.textContent = 'Bot started';
            } else {
                msg.className = 'status-msg status-err';
                msg.textContent = res.error || 'Failed to start';
            }
            setTimeout(() => { msg.style.display = 'none'; }, 3000);
            refreshStatus();
        });
    });
}

function stopBot() {
    fetch('/api/bot/stop', { method:'POST' }).then(r => r.json()).then(res => {
        const msg = document.getElementById('control-msg');
        if (res.status === 'stopped') {
            msg.className = 'status-msg status-ok';
            msg.textContent = 'Bot stopped';
        } else {
            msg.className = 'status-msg status-err';
            msg.textContent = res.error || 'Not running';
        }
        setTimeout(() => { msg.style.display = 'none'; }, 3000);
        refreshStatus();
    });
}

function refreshStatus() {
    fetch('/api/processes').then(r => r.json()).then(data => {
        const el = document.getElementById('bot-status');
        const amm = data.AMM || {};
        if (amm.running) {
            el.innerHTML = '<span class="badge badge-running">RUNNING</span> PID ' + amm.pid;
        } else {
            el.innerHTML = '<span class="badge badge-stopped">STOPPED</span>';
        }
    });
}

loadConfig();
refreshStatus();
setInterval(refreshStatus, 5000);
</script>
</body>
</html>'''
