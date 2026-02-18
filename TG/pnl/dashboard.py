"""
PnL Dashboard — Multi-day analytics for TG Grid Bot and TollGate.

Flask app on port 9000 with 5 tabs:
1. Overview — KPIs, bot comparison, cumulative PnL chart
2. Sessions — Drill-down: session → pairs → cycles → transactions
3. Transactions — Filterable log
4. Inventory — Current positions
5. Analytics — PnL by ticker, by day, by pair, win rate, stats

Usage:
    python -m TG.pnl --port 9000
    python -m TG.pnl.dashboard --port 9000
"""

import argparse
import json
import logging
from datetime import date, datetime

from flask import Flask, Response, jsonify, request

from .db_manager import PnLDBManager

logger = logging.getLogger(__name__)


def _json_serial(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def create_app(db_config=None) -> Flask:
    """Create Flask app with all API endpoints."""
    app = Flask(__name__)
    db = None

    def get_db():
        nonlocal db
        if db is None:
            try:
                db = PnLDBManager(db_config)
            except Exception as e:
                logger.error("Dashboard DB init failed: %s", e)
        return db

    # ── Page Routes ──

    @app.route('/')
    def index():
        return Response(_build_html(), mimetype='text/html')

    # ── API Routes ──

    @app.route('/api/state')
    def api_state():
        """Landing page compatibility — returns basic status."""
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            overview = mgr.get_overview()
            return jsonify({
                'summary': {
                    'total_pnl': overview['all_time_pnl'],
                    'total_cycles': overview['all_time_cycles'],
                    'today_pnl': overview['today_pnl'],
                },
                'status': 'ok',
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/overview')
    def api_overview():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_overview()
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sessions')
    def api_sessions():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            bot_type = request.args.get('bot_type')
            limit = int(request.args.get('limit', 50))
            data = mgr.get_sessions(bot_type, limit)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/sessions/<int:session_id>')
    def api_session_detail(session_id):
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_session_detail(session_id)
            if not data:
                return jsonify({'error': 'Not found'}), 404
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/pairs/<int:pair_id>/cycles')
    def api_pair_cycles(pair_id):
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            limit = int(request.args.get('limit', 200))
            data = mgr.get_pair_cycles(pair_id, limit)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cycles/<int:cycle_id>/txns')
    def api_cycle_txns(cycle_id):
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_cycle_transactions(cycle_id)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/transactions')
    def api_transactions():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_transactions(
                session_id=request.args.get('session_id', type=int),
                bot_type=request.args.get('bot_type'),
                ticker=request.args.get('ticker'),
                txn_type=request.args.get('txn_type'),
                from_date=request.args.get('from'),
                to_date=request.args.get('to'),
                limit=request.args.get('limit', 200, type=int),
                offset=request.args.get('offset', 0, type=int),
            )
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/inventory')
    def api_inventory():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_inventory_current()
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/by-ticker')
    def api_by_ticker():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', type=int)
            data = mgr.get_pnl_by_ticker(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/by-day')
    def api_by_day():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', 30, type=int)
            data = mgr.get_pnl_by_day(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/by-pair')
    def api_by_pair():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', type=int)
            data = mgr.get_pnl_by_pair(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/timeline')
    def api_timeline():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', 30, type=int)
            data = mgr.get_pnl_timeline(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/analytics/stats')
    def api_stats():
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            data = mgr.get_stats()
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app


def _build_html() -> str:
    """Build the single-page dashboard HTML."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PnL Tracker — India-TS</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    :root {
        --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a;
        --text: #e0e0e0; --dim: #666; --green: #00c853;
        --red: #ff1744; --blue: #448aff; --purple: #b388ff;
        --orange: #ff9100;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', monospace;
        background: var(--bg); color: var(--text);
        min-height: 100vh;
    }
    .tab-btn { cursor: pointer; padding: 8px 16px; border-radius: 6px;
               font-size: 12px; border: 1px solid transparent;
               background: transparent; color: var(--dim); transition: all 0.2s; }
    .tab-btn:hover { color: var(--text); }
    .tab-btn.active { background: var(--card); border-color: var(--border);
                      color: var(--purple); }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px; }
    .kpi { text-align: center; }
    .kpi-label { font-size: 10px; text-transform: uppercase; color: var(--dim);
                 margin-bottom: 4px; }
    .kpi-value { font-size: 20px; font-weight: 700; }
    .pnl-pos { color: var(--green); }
    .pnl-neg { color: var(--red); }
    table { width: 100%; border-collapse: collapse; font-size: 11px; }
    th { text-align: left; padding: 8px; color: var(--dim); font-weight: 500;
         border-bottom: 1px solid var(--border); font-size: 10px;
         text-transform: uppercase; }
    td { padding: 8px; border-bottom: 1px solid var(--border); }
    tr:hover td { background: rgba(255,255,255,0.02); }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
             font-size: 10px; font-weight: 600; }
    .badge-active { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-ended { background: rgba(102,102,102,0.15); color: var(--dim); }
    .badge-crashed { background: rgba(255,23,68,0.15); color: var(--red); }
    .badge-open { background: rgba(68,138,255,0.15); color: var(--blue); }
    .badge-closed { background: rgba(0,200,83,0.15); color: var(--green); }
    .badge-cancelled { background: rgba(255,145,0,0.15); color: var(--orange); }
    .drill-link { color: var(--blue); cursor: pointer; text-decoration: none; }
    .drill-link:hover { text-decoration: underline; }
    .breadcrumb { font-size: 11px; color: var(--dim); margin-bottom: 12px; }
    .breadcrumb span { color: var(--blue); cursor: pointer; }
    .breadcrumb span:hover { text-decoration: underline; }
    .filter-input { background: var(--card); border: 1px solid var(--border);
                    border-radius: 6px; padding: 6px 10px; color: var(--text);
                    font-family: inherit; font-size: 11px; }
    .filter-input:focus { outline: none; border-color: var(--purple); }
    select.filter-input { appearance: none; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .chart-wrap { position: relative; height: 250px; }
    .empty-state { text-align: center; padding: 40px; color: var(--dim); }
</style>
</head>
<body class="p-4 md:p-6 max-w-7xl mx-auto">

<!-- HEADER -->
<div class="flex items-center justify-between mb-6">
    <div>
        <h1 class="text-lg font-bold" style="color:var(--purple);">PnL Tracker</h1>
        <div class="text-xs" style="color:var(--dim);">Multi-day analytics — TG Grid & TollGate</div>
    </div>
    <div class="flex gap-2">
        <button class="tab-btn active" data-tab="overview">Overview</button>
        <button class="tab-btn" data-tab="sessions">Sessions</button>
        <button class="tab-btn" data-tab="transactions">Transactions</button>
        <button class="tab-btn" data-tab="inventory">Inventory</button>
        <button class="tab-btn" data-tab="analytics">Analytics</button>
    </div>
    <div class="text-xs" style="color:var(--dim);" id="clock"></div>
</div>

<!-- TAB: OVERVIEW -->
<div id="tab-overview" class="tab-content active">
    <!-- KPI Cards -->
    <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4" id="kpi-grid"></div>

    <!-- Bot Breakdown + Chart -->
    <div class="grid md:grid-cols-2 gap-4">
        <div class="card">
            <div class="text-xs font-semibold mb-3" style="color:var(--dim);">BOT BREAKDOWN (TODAY)</div>
            <table>
                <thead><tr><th>Bot</th><th>PnL</th><th>Cycles</th></tr></thead>
                <tbody id="bot-table"></tbody>
            </table>
        </div>
        <div class="card">
            <div class="text-xs font-semibold mb-3" style="color:var(--dim);">CUMULATIVE PnL</div>
            <div class="chart-wrap"><canvas id="pnl-chart"></canvas></div>
        </div>
    </div>
</div>

<!-- TAB: SESSIONS -->
<div id="tab-sessions" class="tab-content">
    <div id="sessions-breadcrumb" class="breadcrumb"></div>
    <div class="card" id="sessions-content">
        <div class="text-xs font-semibold mb-3" style="color:var(--dim);">SESSIONS</div>
        <table>
            <thead><tr><th>ID</th><th>Bot</th><th>Started</th><th>Status</th><th>PnL</th><th>Cycles</th></tr></thead>
            <tbody id="sessions-table"></tbody>
        </table>
    </div>
</div>

<!-- TAB: TRANSACTIONS -->
<div id="tab-transactions" class="tab-content">
    <div class="card">
        <div class="flex items-center gap-3 mb-3 flex-wrap">
            <div class="text-xs font-semibold" style="color:var(--dim);">TRANSACTIONS</div>
            <select class="filter-input" id="txn-bot-filter">
                <option value="">All Bots</option>
                <option value="tg_grid">TG Grid</option>
                <option value="tollgate">TollGate</option>
            </select>
            <input type="text" class="filter-input" id="txn-ticker-filter" placeholder="Ticker...">
            <select class="filter-input" id="txn-type-filter">
                <option value="">All Types</option>
                <option value="ENTRY">ENTRY</option>
                <option value="TARGET">TARGET</option>
                <option value="PAIR_HEDGE">PAIR_HEDGE</option>
                <option value="PAIR_UNWIND">PAIR_UNWIND</option>
            </select>
            <button class="tab-btn" onclick="loadTransactions()" style="font-size:11px;">Filter</button>
        </div>
        <table>
            <thead><tr><th>Time</th><th>Bot</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Price</th><th>Type</th><th>PnL</th><th>Running</th></tr></thead>
            <tbody id="txn-table"></tbody>
        </table>
    </div>
</div>

<!-- TAB: INVENTORY -->
<div id="tab-inventory" class="tab-content">
    <div class="card">
        <div class="text-xs font-semibold mb-3" style="color:var(--dim);">CURRENT POSITIONS</div>
        <table>
            <thead><tr><th>Ticker</th><th>Bot</th><th>Net Qty</th><th>Avg Price</th><th>Updated</th></tr></thead>
            <tbody id="inv-table"></tbody>
        </table>
    </div>
</div>

<!-- TAB: ANALYTICS -->
<div id="tab-analytics" class="tab-content">
    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="stats-grid"></div>

    <div class="grid md:grid-cols-2 gap-4 mb-4">
        <!-- PnL by Ticker -->
        <div class="card">
            <div class="text-xs font-semibold mb-3" style="color:var(--dim);">PnL BY TICKER</div>
            <div class="chart-wrap"><canvas id="ticker-chart"></canvas></div>
        </div>
        <!-- PnL by Day -->
        <div class="card">
            <div class="text-xs font-semibold mb-3" style="color:var(--dim);">PnL BY DAY</div>
            <div class="chart-wrap"><canvas id="day-chart"></canvas></div>
        </div>
    </div>
    <!-- PnL by Pair -->
    <div class="card">
        <div class="text-xs font-semibold mb-3" style="color:var(--dim);">PnL BY PAIR</div>
        <table>
            <thead><tr><th>Primary</th><th>Secondary</th><th>Type</th><th>PnL</th><th>Txns</th></tr></thead>
            <tbody id="pair-table"></tbody>
        </table>
    </div>
</div>

<script>
// ── Tab Navigation ──
const tabs = document.querySelectorAll('.tab-btn[data-tab]');
tabs.forEach(btn => btn.addEventListener('click', () => {
    tabs.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    const loader = tabLoaders[btn.dataset.tab];
    if (loader) loader();
}));

// ── Utilities ──
function fmtPnl(v) {
    if (v == null || isNaN(v)) return '<span style="color:var(--dim)">—</span>';
    const cls = v >= 0 ? 'pnl-pos' : 'pnl-neg';
    return `<span class="${cls}">${v >= 0 ? '+' : ''}${v.toFixed(2)}</span>`;
}
function fmtTs(ts) {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleString('en-IN', {timeZone:'Asia/Kolkata', month:'short', day:'numeric',
        hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false});
}
function fmtDate(ts) {
    if (!ts) return '—';
    const d = new Date(ts);
    return d.toLocaleDateString('en-IN', {timeZone:'Asia/Kolkata', month:'short', day:'numeric'});
}
function badge(status) {
    const cls = {active:'badge-active', ended:'badge-ended', crashed:'badge-crashed',
                 open:'badge-open', closed:'badge-closed', cancelled:'badge-cancelled'}[status] || '';
    return `<span class="badge ${cls}">${status}</span>`;
}

// ── Charts ──
let pnlChart = null, tickerChart = null, dayChart = null;

function destroyChart(c) { if (c) c.destroy(); return null; }

const chartDefaults = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
        x: { ticks: { color: '#666', font: { family: 'JetBrains Mono', size: 10 } },
             grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#666', font: { family: 'JetBrains Mono', size: 10 } },
             grid: { color: 'rgba(255,255,255,0.04)' } }
    }
};

// ── Tab Loaders ──
const tabLoaders = {
    overview: loadOverview,
    sessions: loadSessions,
    transactions: loadTransactions,
    inventory: loadInventory,
    analytics: loadAnalytics,
};

// ── Overview ──
function loadOverview() {
    fetch('/api/overview').then(r => r.json()).then(d => {
        const kpis = [
            {label: 'Today PnL', value: fmtPnl(d.today_pnl)},
            {label: 'Today Cycles', value: `<span style="color:var(--blue)">${d.today_cycles}</span>`},
            {label: 'Week PnL', value: fmtPnl(d.week_pnl)},
            {label: 'All-Time PnL', value: fmtPnl(d.all_time_pnl)},
            {label: 'All-Time Cycles', value: `<span style="color:var(--blue)">${d.all_time_cycles}</span>`},
        ];
        document.getElementById('kpi-grid').innerHTML = kpis.map(k =>
            `<div class="card kpi"><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div>`
        ).join('');

        // Bot breakdown
        const tbody = document.getElementById('bot-table');
        if (d.bot_breakdown && d.bot_breakdown.length) {
            tbody.innerHTML = d.bot_breakdown.map(b =>
                `<tr><td>${b.bot_type}</td><td>${fmtPnl(b.pnl)}</td><td>${b.cycles}</td></tr>`
            ).join('');
        } else {
            tbody.innerHTML = '<tr><td colspan="3" style="color:var(--dim);text-align:center;">No data today</td></tr>';
        }
    }).catch(() => {
        document.getElementById('kpi-grid').innerHTML =
            '<div class="card" style="grid-column:1/-1;text-align:center;color:var(--dim);">DB unavailable</div>';
    });

    // Timeline chart
    fetch('/api/analytics/timeline?days=30').then(r => r.json()).then(data => {
        pnlChart = destroyChart(pnlChart);
        if (!data.length) return;
        const ctx = document.getElementById('pnl-chart').getContext('2d');
        pnlChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => fmtTs(d.ts)),
                datasets: [{
                    data: data.map(d => d.cumulative_pnl),
                    borderColor: '#b388ff', borderWidth: 1.5,
                    pointRadius: 0, fill: true,
                    backgroundColor: 'rgba(179,136,255,0.08)',
                }]
            },
            options: {...chartDefaults, scales: {
                ...chartDefaults.scales,
                x: {...chartDefaults.scales.x, display: false}
            }}
        });
    }).catch(() => {});
}

// ── Sessions (with drill-down) ──
let sessionsDrillState = null;

function loadSessions() {
    sessionsDrillState = null;
    document.getElementById('sessions-breadcrumb').innerHTML = '';
    fetch('/api/sessions').then(r => r.json()).then(data => {
        const tbody = document.getElementById('sessions-table');
        const content = document.getElementById('sessions-content');
        content.querySelector('.text-xs').textContent = 'SESSIONS';

        // Reset table headers
        content.querySelector('thead tr').innerHTML =
            '<th>ID</th><th>Bot</th><th>Started</th><th>Status</th><th>PnL</th><th>Cycles</th>';

        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No sessions yet</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(s =>
            `<tr>
                <td><span class="drill-link" onclick="drillSession(${s.session_id})">${s.session_id}</span></td>
                <td>${s.bot_type}</td>
                <td>${fmtTs(s.started_at)}</td>
                <td>${badge(s.status)}</td>
                <td>${fmtPnl(s.total_pnl)}</td>
                <td>${s.total_cycles}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

function drillSession(sid) {
    sessionsDrillState = {level: 'session', session_id: sid};
    document.getElementById('sessions-breadcrumb').innerHTML =
        `<span onclick="loadSessions()">Sessions</span> / Session #${sid}`;

    fetch(`/api/sessions/${sid}`).then(r => r.json()).then(data => {
        const content = document.getElementById('sessions-content');
        content.querySelector('.text-xs').textContent = `SESSION #${sid} — PAIRS`;
        content.querySelector('thead tr').innerHTML =
            '<th>Pair ID</th><th>Primary</th><th>Secondary</th><th>Type</th><th>Anchor</th><th>PnL</th><th>Cycles</th>';

        const tbody = document.getElementById('sessions-table');
        const pairs = data.pairs || [];
        if (!pairs.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No pairs</td></tr>';
            return;
        }
        tbody.innerHTML = pairs.map(p =>
            `<tr>
                <td><span class="drill-link" onclick="drillPair(${sid}, ${p.pair_id})">${p.pair_id}</span></td>
                <td>${p.primary_ticker}</td>
                <td>${p.secondary_ticker || '—'}</td>
                <td>${p.pair_type}</td>
                <td>${p.anchor_price ? p.anchor_price.toFixed(2) : '—'}</td>
                <td>${fmtPnl(p.pair_pnl)}</td>
                <td>${p.pair_cycles}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

function drillPair(sid, pid) {
    sessionsDrillState = {level: 'pair', session_id: sid, pair_id: pid};
    document.getElementById('sessions-breadcrumb').innerHTML =
        `<span onclick="loadSessions()">Sessions</span> / <span onclick="drillSession(${sid})">Session #${sid}</span> / Pair #${pid}`;

    fetch(`/api/pairs/${pid}/cycles`).then(r => r.json()).then(data => {
        const content = document.getElementById('sessions-content');
        content.querySelector('.text-xs').textContent = `PAIR #${pid} — CYCLES`;
        content.querySelector('thead tr').innerHTML =
            '<th>Cycle</th><th>Group</th><th>Bot</th><th>Side</th><th>Level</th><th>Entry</th><th>Target</th><th>PnL</th><th>Status</th>';

        const tbody = document.getElementById('sessions-table');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No cycles</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(c =>
            `<tr>
                <td><span class="drill-link" onclick="drillCycle(${sid}, ${pid}, ${c.cycle_id})">${c.cycle_id}</span></td>
                <td style="font-size:10px;">${c.group_id}</td>
                <td>${c.bot_id}</td>
                <td>${c.entry_side}</td>
                <td>${c.grid_level}</td>
                <td>${c.entry_fill_price ? c.entry_fill_price.toFixed(2) : (c.entry_price ? c.entry_price.toFixed(2) : '—')}</td>
                <td>${c.target_fill_price ? c.target_fill_price.toFixed(2) : (c.target_price ? c.target_price.toFixed(2) : '—')}</td>
                <td>${fmtPnl(c.combined_pnl)}</td>
                <td>${badge(c.status)}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

function drillCycle(sid, pid, cid) {
    document.getElementById('sessions-breadcrumb').innerHTML =
        `<span onclick="loadSessions()">Sessions</span> / <span onclick="drillSession(${sid})">Session #${sid}</span> / <span onclick="drillPair(${sid}, ${pid})">Pair #${pid}</span> / Cycle #${cid}`;

    fetch(`/api/cycles/${cid}/txns`).then(r => r.json()).then(data => {
        const content = document.getElementById('sessions-content');
        content.querySelector('.text-xs').textContent = `CYCLE #${cid} — TRANSACTIONS`;
        content.querySelector('thead tr').innerHTML =
            '<th>Time</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Price</th><th>Type</th><th>PnL</th><th>Order</th>';

        const tbody = document.getElementById('sessions-table');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No transactions</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(t =>
            `<tr>
                <td>${fmtTs(t.ts)}</td>
                <td>${t.ticker}</td>
                <td style="color:${t.side === 'BUY' ? 'var(--green)' : 'var(--red)'};">${t.side}</td>
                <td>${t.qty}</td>
                <td>${t.price.toFixed(2)}</td>
                <td>${t.txn_type}</td>
                <td>${fmtPnl(t.pnl_increment)}</td>
                <td style="font-size:10px;">${t.order_id ? t.order_id.slice(-8) : '—'}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

// ── Transactions ──
function loadTransactions() {
    const bot = document.getElementById('txn-bot-filter').value;
    const ticker = document.getElementById('txn-ticker-filter').value;
    const type = document.getElementById('txn-type-filter').value;
    let url = '/api/transactions?limit=200';
    if (bot) url += `&bot_type=${bot}`;
    if (ticker) url += `&ticker=${ticker}`;
    if (type) url += `&txn_type=${type}`;

    fetch(url).then(r => r.json()).then(data => {
        const tbody = document.getElementById('txn-table');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No transactions</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(t =>
            `<tr>
                <td>${fmtTs(t.ts)}</td>
                <td>${t.bot_type}</td>
                <td>${t.ticker}</td>
                <td style="color:${t.side === 'BUY' ? 'var(--green)' : 'var(--red)'};">${t.side}</td>
                <td>${t.qty}</td>
                <td>${t.price.toFixed(2)}</td>
                <td>${t.txn_type}</td>
                <td>${fmtPnl(t.pnl_increment)}</td>
                <td>${fmtPnl(t.running_session_pnl)}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

// ── Inventory ──
function loadInventory() {
    fetch('/api/inventory').then(r => r.json()).then(data => {
        const tbody = document.getElementById('inv-table');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No open positions</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(i =>
            `<tr>
                <td>${i.ticker}</td>
                <td>${i.bot_type}</td>
                <td style="color:${i.net_qty > 0 ? 'var(--green)' : i.net_qty < 0 ? 'var(--red)' : 'var(--dim)'};">
                    ${i.net_qty > 0 ? '+' : ''}${i.net_qty}</td>
                <td>${i.avg_price ? i.avg_price.toFixed(2) : '—'}</td>
                <td>${fmtTs(i.updated_at)}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

// ── Analytics ──
function loadAnalytics() {
    // Stats
    fetch('/api/analytics/stats').then(r => r.json()).then(d => {
        const stats = [
            {label: 'Win Rate', value: `<span style="color:var(--green)">${d.win_rate}%</span>`},
            {label: 'Avg PnL/Cycle', value: fmtPnl(d.avg_pnl)},
            {label: 'Best Cycle', value: fmtPnl(d.best_cycle)},
            {label: 'Worst Cycle', value: fmtPnl(d.worst_cycle)},
        ];
        document.getElementById('stats-grid').innerHTML = stats.map(s =>
            `<div class="card kpi"><div class="kpi-label">${s.label}</div><div class="kpi-value">${s.value}</div></div>`
        ).join('');
    }).catch(() => {});

    // PnL by Ticker
    fetch('/api/analytics/by-ticker').then(r => r.json()).then(data => {
        tickerChart = destroyChart(tickerChart);
        if (!data.length) return;
        const ctx = document.getElementById('ticker-chart').getContext('2d');
        tickerChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.ticker),
                datasets: [{
                    data: data.map(d => d.total_pnl),
                    backgroundColor: data.map(d => d.total_pnl >= 0
                        ? 'rgba(0,200,83,0.6)' : 'rgba(255,23,68,0.6)'),
                    borderRadius: 4,
                }]
            },
            options: chartDefaults,
        });
    }).catch(() => {});

    // PnL by Day
    fetch('/api/analytics/by-day?days=30').then(r => r.json()).then(data => {
        dayChart = destroyChart(dayChart);
        if (!data.length) return;
        const ctx = document.getElementById('day-chart').getContext('2d');
        dayChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => fmtDate(d.day)),
                datasets: [{
                    data: data.map(d => d.daily_pnl),
                    backgroundColor: data.map(d => d.daily_pnl >= 0
                        ? 'rgba(0,200,83,0.6)' : 'rgba(255,23,68,0.6)'),
                    borderRadius: 4,
                }]
            },
            options: chartDefaults,
        });
    }).catch(() => {});

    // PnL by Pair
    fetch('/api/analytics/by-pair').then(r => r.json()).then(data => {
        const tbody = document.getElementById('pair-table');
        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No data</td></tr>';
            return;
        }
        tbody.innerHTML = data.map(p =>
            `<tr>
                <td>${p.primary_ticker}</td>
                <td>${p.secondary_ticker || '—'}</td>
                <td>${p.pair_type}</td>
                <td>${fmtPnl(p.total_pnl)}</td>
                <td>${p.txn_count}</td>
            </tr>`
        ).join('');
    }).catch(() => {});
}

// ── Clock + Auto-refresh ──
function updateClock() {
    document.getElementById('clock').textContent =
        new Date().toLocaleString('en-IN', {timeZone:'Asia/Kolkata',
            hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false});
}

// Initial load
loadOverview();
updateClock();
setInterval(updateClock, 1000);
setInterval(() => {
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab && activeTab.dataset.tab === 'overview') loadOverview();
    if (activeTab && activeTab.dataset.tab === 'inventory') loadInventory();
}, 5000);
</script>
</body>
</html>'''


def main():
    """CLI entry point for the dashboard."""
    parser = argparse.ArgumentParser(description='PnL Tracker Dashboard')
    parser.add_argument('--port', type=int, default=9000, help='Port (default: 9000)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    app = create_app()
    logger.info("Starting PnL Dashboard on %s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
