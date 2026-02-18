"""
PnL Dashboard — Account-based daily reports for TG trading accounts.

Flask app on port 9000 with 2 tabs:
1. 01MU01 (SPCENET) — TollGate bot daily reports
2. 01MU06 (Grid) — TG Grid bot daily reports (TATSILV/TATAGOLD/IDEA + hedges)

Usage:
    python -m TG.pnl --port 9000
    python -m TG.pnl.dashboard --port 9000
"""

import argparse
import json
import logging
from datetime import date, datetime
from decimal import Decimal

from flask import Flask, Response, jsonify, request

from .db_manager import PnLDBManager

logger = logging.getLogger(__name__)


def _json_serial(obj):
    """JSON serializer for datetime, date, and Decimal objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


def create_app(db_config=None) -> Flask:
    """Create Flask app with account-based daily report endpoints."""
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

    @app.route('/api/tollgate/daily')
    def api_tollgate_daily():
        """01MU01 day-by-day summaries."""
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', 90, type=int)
            data = mgr.get_daily_summary_tollgate(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            logger.error("tollgate/daily error: %s", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/grid/daily')
    def api_grid_daily():
        """01MU06 day-by-day summaries (primaries + hedges)."""
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            days = request.args.get('days', 90, type=int)
            data = mgr.get_daily_summary_grid(days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            logger.error("grid/daily error: %s", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/day-transactions')
    def api_day_transactions():
        """Transaction drill-down for a specific bot/day/ticker."""
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            bot_type = request.args.get('bot_type')
            day = request.args.get('day')
            ticker = request.args.get('ticker')
            if not bot_type or not day:
                return jsonify({'error': 'bot_type and day required'}), 400
            data = mgr.get_day_transactions(bot_type, day, ticker)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            logger.error("day-transactions error: %s", e)
            return jsonify({'error': str(e)}), 500

    @app.route('/api/cumulative-pnl')
    def api_cumulative_pnl():
        """Cumulative PnL chart data for a bot type."""
        mgr = get_db()
        if not mgr:
            return jsonify({'error': 'DB unavailable'}), 503
        try:
            bot_type = request.args.get('bot_type')
            days = request.args.get('days', 90, type=int)
            if not bot_type:
                return jsonify({'error': 'bot_type required'}), 400
            data = mgr.get_cumulative_pnl(bot_type, days)
            return Response(
                json.dumps(data, default=_json_serial),
                mimetype='application/json')
        except Exception as e:
            logger.error("cumulative-pnl error: %s", e)
            return jsonify({'error': str(e)}), 500

    return app


def _build_html() -> str:
    """Build the 2-tab account-based daily report dashboard."""
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
        --orange: #ff9100; --cyan: #00e5ff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', monospace;
        background: var(--bg); color: var(--text);
        min-height: 100vh;
    }
    .tab-btn { cursor: pointer; padding: 8px 20px; border-radius: 6px;
               font-size: 12px; border: 1px solid transparent;
               background: transparent; color: var(--dim); transition: all 0.2s;
               font-family: inherit; }
    .tab-btn:hover { color: var(--text); }
    .tab-btn.active { background: var(--card); border-color: var(--border);
                      color: var(--purple); }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px; margin-bottom: 12px; }
    .kpi { text-align: center; }
    .kpi-label { font-size: 10px; text-transform: uppercase; color: var(--dim);
                 margin-bottom: 4px; }
    .kpi-value { font-size: 20px; font-weight: 700; }
    .pnl-pos { color: var(--green); }
    .pnl-neg { color: var(--red); }
    .pnl-zero { color: var(--dim); }
    .day-card { background: var(--card); border: 1px solid var(--border);
                border-radius: 10px; margin-bottom: 8px; overflow: hidden; }
    .day-header { display: flex; justify-content: space-between; align-items: center;
                  padding: 12px 16px; cursor: pointer; }
    .day-header:hover { background: rgba(255,255,255,0.02); }
    .day-date { font-size: 13px; font-weight: 600; }
    .day-weekday { font-size: 11px; color: var(--dim); margin-left: 8px; }
    .day-pnl { font-size: 14px; font-weight: 700; }
    .day-body { padding: 0 16px 12px; font-size: 11px; }
    .day-row { display: flex; justify-content: space-between; align-items: center;
               padding: 4px 0; }
    .day-divider { border-top: 1px solid var(--border); margin: 8px 0; }
    .ticker-block { padding: 6px 0; }
    .ticker-name { font-size: 12px; font-weight: 600; color: var(--cyan); }
    .ticker-pnl { font-size: 12px; font-weight: 700; }
    .hedge-block { padding: 8px 0; border-top: 1px dashed var(--border); margin-top: 4px; }
    .hedge-label { font-size: 10px; text-transform: uppercase; color: var(--orange);
                   font-weight: 600; margin-bottom: 4px; }
    .expand-btn { font-size: 10px; color: var(--blue); cursor: pointer;
                  padding: 6px 0; }
    .expand-btn:hover { text-decoration: underline; }
    .txn-table { width: 100%; border-collapse: collapse; font-size: 10px;
                 margin-top: 8px; }
    .txn-table th { text-align: left; padding: 6px 8px; color: var(--dim);
                    font-weight: 500; border-bottom: 1px solid var(--border);
                    text-transform: uppercase; font-size: 9px; }
    .txn-table td { padding: 6px 8px; border-bottom: 1px solid rgba(42,45,58,0.5); }
    .txn-table tr:hover td { background: rgba(255,255,255,0.02); }
    .chart-wrap { position: relative; height: 150px; margin-bottom: 16px; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .loading { text-align: center; padding: 40px; color: var(--dim); font-size: 12px; }
    .dim { color: var(--dim); }
    .inv-badge { display: inline-block; padding: 1px 6px; border-radius: 3px;
                 font-size: 10px; font-weight: 600; }
    .inv-long { background: rgba(0,200,83,0.12); color: var(--green); }
    .inv-short { background: rgba(255,23,68,0.12); color: var(--red); }
    .inv-flat { background: rgba(102,102,102,0.12); color: var(--dim); }
</style>
</head>
<body class="p-4 md:p-6 max-w-5xl mx-auto">

<!-- HEADER -->
<div class="flex items-center justify-between mb-6">
    <div>
        <h1 class="text-lg font-bold" style="color:var(--purple);">PnL Tracker</h1>
        <div class="text-xs" style="color:var(--dim);">Account-based daily reports</div>
    </div>
    <div class="flex gap-2">
        <button class="tab-btn active" data-tab="01mu01">01MU01 (SPCENET)</button>
        <button class="tab-btn" data-tab="01mu06">01MU06 (Grid)</button>
    </div>
    <div class="text-xs" style="color:var(--dim);" id="clock"></div>
</div>

<!-- TAB: 01MU01 -->
<div id="tab-01mu01" class="tab-content active">
    <div class="text-sm font-bold mb-3" style="color:var(--purple);">01MU01 — SPCENET TollGate</div>
    <div class="card" style="padding:12px 16px;">
        <div class="chart-wrap"><canvas id="chart-tollgate"></canvas></div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="kpi-tollgate"></div>
    <div id="days-tollgate"><div class="loading">Loading...</div></div>
</div>

<!-- TAB: 01MU06 -->
<div id="tab-01mu06" class="tab-content">
    <div class="text-sm font-bold mb-3" style="color:var(--purple);">01MU06 — TG Grid (TATSILV / TATAGOLD / IDEA)</div>
    <div class="card" style="padding:12px 16px;">
        <div class="chart-wrap"><canvas id="chart-grid"></canvas></div>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4" id="kpi-grid"></div>
    <div id="days-grid"><div class="loading">Loading...</div></div>
</div>

<script>
// ── Tab Navigation ──
const tabs = document.querySelectorAll('.tab-btn[data-tab]');
const tabLoaders = { '01mu01': load01MU01, '01mu06': load01MU06 };
const tabLoaded = {};

tabs.forEach(btn => btn.addEventListener('click', () => {
    tabs.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (!tabLoaded[btn.dataset.tab]) {
        tabLoaders[btn.dataset.tab]();
        tabLoaded[btn.dataset.tab] = true;
    }
}));

// ── Utilities ──
const WEEKDAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function fmtPnl(v) {
    if (v == null || isNaN(v)) return '<span class="pnl-zero">0.00</span>';
    if (v === 0) return '<span class="pnl-zero">0.00</span>';
    const cls = v > 0 ? 'pnl-pos' : 'pnl-neg';
    return `<span class="${cls}">${v > 0 ? '+' : ''}${v.toFixed(2)}</span>`;
}

function fmtQty(v) {
    if (v == null) return '0';
    return v.toLocaleString('en-IN');
}

function fmtInv(v) {
    if (v == null || v === 0) return '<span class="inv-badge inv-flat">0</span>';
    const cls = v > 0 ? 'inv-long' : 'inv-short';
    return `<span class="inv-badge ${cls}">${v > 0 ? '+' : ''}${fmtQty(v)}</span>`;
}

function fmtPrice(v) {
    if (!v || v === 0) return '<span class="dim">--</span>';
    return v.toFixed(4);
}

function fmtTs(ts) {
    if (!ts) return '--';
    const d = new Date(ts);
    return d.toLocaleString('en-IN', {timeZone:'Asia/Kolkata',
        hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false});
}

function dayLabel(isoDay) {
    // isoDay = "2026-02-18"
    const d = new Date(isoDay + 'T00:00:00');
    const wd = WEEKDAYS[d.getDay()];
    const parts = isoDay.split('-');
    return `${parts[0]}-${parts[1]}-${parts[2]}  ${wd}`;
}

// ── Charts ──
let chartTollgate = null, chartGrid = null;

function destroyChart(c) { if (c) c.destroy(); return null; }

const chartOpts = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false },
        tooltip: { callbacks: { label: ctx => (ctx.parsed.y >= 0 ? '+' : '') + ctx.parsed.y.toFixed(2) } }
    },
    scales: {
        x: { ticks: { color: '#666', font: { family: 'JetBrains Mono', size: 9 }, maxRotation: 0 },
             grid: { color: 'rgba(255,255,255,0.04)' } },
        y: { ticks: { color: '#666', font: { family: 'JetBrains Mono', size: 9 } },
             grid: { color: 'rgba(255,255,255,0.04)' } }
    }
};

function renderCumulativeChart(canvasId, data) {
    const existing = canvasId === 'chart-tollgate' ? chartTollgate : chartGrid;
    if (existing) existing.destroy();
    if (!data.length) return;
    const ctx = document.getElementById(canvasId).getContext('2d');
    const chart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(d => {
                const p = d.day.split('-');
                return p[1] + '-' + p[2];
            }),
            datasets: [{
                data: data.map(d => d.cumulative_pnl),
                borderColor: '#b388ff', borderWidth: 1.5,
                pointRadius: 2, pointBackgroundColor: '#b388ff',
                fill: true, backgroundColor: 'rgba(179,136,255,0.08)',
            }]
        },
        options: chartOpts,
    });
    if (canvasId === 'chart-tollgate') chartTollgate = chart;
    else chartGrid = chart;
}

// ── Expand Day Transactions ──
async function expandDay(botType, day, containerId, ticker) {
    const el = document.getElementById(containerId);
    if (el.innerHTML) { el.innerHTML = ''; return; }
    el.innerHTML = '<div class="dim" style="padding:8px;font-size:10px;">Loading...</div>';
    let url = `/api/day-transactions?bot_type=${botType}&day=${day}`;
    if (ticker) url += `&ticker=${ticker}`;
    try {
        const resp = await fetch(url);
        const data = await resp.json();
        if (!data.length) { el.innerHTML = '<div class="dim" style="padding:8px;font-size:10px;">No transactions</div>'; return; }
        let html = `<table class="txn-table">
            <thead><tr><th>Time</th><th>Ticker</th><th>Side</th><th>Qty</th><th>Price</th><th>Type</th><th>PnL</th></tr></thead><tbody>`;
        data.forEach(t => {
            const sideColor = t.side === 'BUY' ? 'var(--green)' : 'var(--red)';
            html += `<tr>
                <td>${fmtTs(t.ts)}</td>
                <td>${t.ticker}</td>
                <td style="color:${sideColor}">${t.side}</td>
                <td>${fmtQty(t.qty)}</td>
                <td>${t.price.toFixed(4)}</td>
                <td>${t.txn_type}</td>
                <td>${fmtPnl(t.pnl_increment)}</td>
            </tr>`;
        });
        html += '</tbody></table>';
        el.innerHTML = html;
    } catch(e) {
        el.innerHTML = '<div class="dim" style="padding:8px;font-size:10px;">Error loading transactions</div>';
    }
}

// ── 01MU01 (TollGate) ──
async function load01MU01() {
    const daysEl = document.getElementById('days-tollgate');
    const kpiEl = document.getElementById('kpi-tollgate');

    // Fetch both in parallel
    const [dailyResp, cumResp] = await Promise.all([
        fetch('/api/tollgate/daily?days=90'),
        fetch('/api/cumulative-pnl?bot_type=tollgate&days=90')
    ]);
    const daily = await dailyResp.json();
    const cumData = await cumResp.json();

    // Chart
    renderCumulativeChart('chart-tollgate', cumData);

    // KPIs
    const allTimePnl = cumData.length ? cumData[cumData.length - 1].cumulative_pnl : 0;
    const todayRow = daily.length ? daily[0] : null;
    const todayPnl = todayRow ? todayRow.pnl : 0;
    const totalRTs = daily.reduce((s, d) => s + d.round_trips, 0);
    const currentInv = todayRow ? todayRow.eod_inventory : 0;

    kpiEl.innerHTML = [
        {label: 'All-Time PnL', value: fmtPnl(allTimePnl)},
        {label: 'Today PnL', value: fmtPnl(todayPnl)},
        {label: 'Total Round Trips', value: `<span style="color:var(--blue)">${totalRTs}</span>`},
        {label: 'Current Inventory', value: fmtInv(currentInv)},
    ].map(k => `<div class="card kpi"><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div>`).join('');

    // Day cards
    if (!daily.length) {
        daysEl.innerHTML = '<div class="loading">No data yet</div>';
        return;
    }

    daysEl.innerHTML = daily.map((d, i) => {
        const txnId = `txn-tollgate-${i}`;
        return `<div class="day-card">
            <div class="day-header" onclick="document.getElementById('body-tg-${i}').style.display = document.getElementById('body-tg-${i}').style.display === 'none' ? 'block' : 'none'">
                <div><span class="day-date">${dayLabel(d.day)}</span></div>
                <div class="day-pnl">${fmtPnl(d.pnl)}</div>
            </div>
            <div class="day-body" id="body-tg-${i}">
                <div class="day-row">
                    <span>Round Trips: <b>${d.round_trips}</b></span>
                    <span>SOD: ${fmtInv(d.sod_inventory)}  EOD: ${fmtInv(d.eod_inventory)}</span>
                </div>
                <div class="day-row">
                    <span>Buy VWAP: <b>${fmtPrice(d.buy_vwap)}</b> (${fmtQty(d.buy_qty)})</span>
                    <span>Sell VWAP: <b>${fmtPrice(d.sell_vwap)}</b> (${fmtQty(d.sell_qty)})</span>
                </div>
                <div class="expand-btn" onclick="expandDay('tollgate','${d.day}','${txnId}')">Toggle transactions</div>
                <div id="${txnId}"></div>
            </div>
        </div>`;
    }).join('');
}

// ── 01MU06 (Grid) ──
async function load01MU06() {
    const daysEl = document.getElementById('days-grid');
    const kpiEl = document.getElementById('kpi-grid');

    const [dailyResp, cumResp] = await Promise.all([
        fetch('/api/grid/daily?days=90'),
        fetch('/api/cumulative-pnl?bot_type=tg_grid&days=90')
    ]);
    const daily = await dailyResp.json();
    const cumData = await cumResp.json();

    // Chart
    renderCumulativeChart('chart-grid', cumData);

    // Group primaries by day
    const dayMap = {};
    (daily.primaries || []).forEach(p => {
        if (!dayMap[p.day]) dayMap[p.day] = { tickers: [], hedge: null };
        dayMap[p.day].tickers.push(p);
    });

    // Merge hedges
    const hedgeMap = {};
    (daily.hedges || []).forEach(h => { hedgeMap[h.day] = h; });

    const days = Object.keys(dayMap).sort().reverse();

    // KPIs
    const allTimePnl = cumData.length ? cumData[cumData.length - 1].cumulative_pnl : 0;
    let todayCombined = 0;
    let totalRTs = 0;
    let totalHedgeCost = 0;

    days.forEach(day => {
        const tickers = dayMap[day].tickers;
        tickers.forEach(t => { totalRTs += t.round_trips; });
    });
    if (days.length) {
        const today = days[0];
        dayMap[today].tickers.forEach(t => { todayCombined += t.combined_pnl; });
    }
    Object.values(hedgeMap).forEach(h => { totalHedgeCost += h.hedge_cost; });

    kpiEl.innerHTML = [
        {label: 'All-Time PnL', value: fmtPnl(allTimePnl)},
        {label: 'Today PnL', value: fmtPnl(todayCombined)},
        {label: 'Total Round Trips', value: `<span style="color:var(--blue)">${totalRTs}</span>`},
        {label: 'Total Hedge Cost', value: fmtPnl(totalHedgeCost)},
    ].map(k => `<div class="card kpi"><div class="kpi-label">${k.label}</div><div class="kpi-value">${k.value}</div></div>`).join('');

    if (!days.length) {
        daysEl.innerHTML = '<div class="loading">No data yet</div>';
        return;
    }

    daysEl.innerHTML = days.map((day, i) => {
        const tickers = dayMap[day].tickers;
        const hedge = hedgeMap[day];
        const dayPnl = tickers.reduce((s, t) => s + t.combined_pnl, 0);
        const txnId = `txn-grid-${i}`;

        let tickerHtml = tickers.map(t => `
            <div class="ticker-block">
                <div class="day-row">
                    <span class="ticker-name">${t.ticker}</span>
                    <span class="ticker-pnl">${fmtPnl(t.combined_pnl)}</span>
                </div>
                <div class="day-row dim">
                    <span>RT: ${t.round_trips}  SOD: ${fmtInv(t.sod_inventory)}  EOD: ${fmtInv(t.eod_inventory)}</span>
                </div>
                <div class="day-row dim">
                    <span>Buy: ${fmtPrice(t.buy_vwap)} (${fmtQty(t.buy_qty)})</span>
                    <span>Sell: ${fmtPrice(t.sell_vwap)} (${fmtQty(t.sell_qty)})</span>
                </div>
                ${t.pair_pnl ? `<div class="day-row dim"><span>Primary: ${fmtPnl(t.primary_pnl)}  Hedge: ${fmtPnl(t.pair_pnl)}</span></div>` : ''}
            </div>
        `).join('');

        let hedgeHtml = '';
        if (hedge) {
            hedgeHtml = `<div class="hedge-block">
                <div class="hedge-label">Hedges (SPCENET)</div>
                <div class="day-row dim">
                    <span>Placed: ${hedge.hedges_placed}  Unwound: ${hedge.hedges_unwound}</span>
                    <span>Cost: ${fmtPnl(hedge.hedge_cost)}</span>
                </div>
                <div class="day-row dim">
                    <span>Hedge Qty: ${fmtQty(hedge.hedge_qty)}  Unwind Qty: ${fmtQty(hedge.unwind_qty)}</span>
                </div>
            </div>`;
        }

        return `<div class="day-card">
            <div class="day-header" onclick="document.getElementById('body-grid-${i}').style.display = document.getElementById('body-grid-${i}').style.display === 'none' ? 'block' : 'none'">
                <div><span class="day-date">${dayLabel(day)}</span></div>
                <div class="day-pnl">Combined ${fmtPnl(dayPnl)}</div>
            </div>
            <div class="day-body" id="body-grid-${i}">
                ${tickerHtml}
                ${hedgeHtml}
                <div class="expand-btn" onclick="expandDay('tg_grid','${day}','${txnId}')">Toggle transactions</div>
                <div id="${txnId}"></div>
            </div>
        </div>`;
    }).join('');
}

// ── Clock ──
function updateClock() {
    document.getElementById('clock').textContent =
        new Date().toLocaleString('en-IN', {timeZone:'Asia/Kolkata',
            hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false});
}

// ── Init ──
load01MU01();
tabLoaded['01mu01'] = true;
updateClock();
setInterval(updateClock, 1000);

// Auto-refresh active tab every 30s
setInterval(() => {
    const activeTab = document.querySelector('.tab-btn.active');
    if (activeTab) {
        tabLoaded[activeTab.dataset.tab] = false;
        tabLoaders[activeTab.dataset.tab]();
        tabLoaded[activeTab.dataset.tab] = true;
    }
}, 30000);
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
