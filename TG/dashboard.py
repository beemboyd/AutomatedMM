"""
TG Grid Bot Dashboard — Live web dashboard on port 7777.

Reads state from TG/state/{SYMBOL}_grid_state.json and serves a
self-contained HTML dashboard with auto-refresh.

Usage:
    python -m TG.dashboard --symbol TATSILV --port 7777
"""

import argparse
import json
import os
import logging
from datetime import datetime

from flask import Flask, jsonify, Response

logger = logging.getLogger(__name__)

STATE_DIR = os.path.join(os.path.dirname(__file__), 'state')


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


def _compute_summary(state: dict) -> dict:
    """Derive KPI metrics from raw state."""
    if not state:
        return {}

    open_groups = state.get('open_groups', {})
    closed_groups = state.get('closed_groups', [])
    total_pnl = state.get('total_pnl', 0.0)
    total_cycles = state.get('total_cycles', 0)

    # Bot split
    bot_a_entry = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'ENTRY_PENDING')
    bot_a_target = sum(1 for g in open_groups.values() if g.get('bot') == 'A' and g.get('status') == 'TARGET_PENDING')
    bot_b_entry = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'ENTRY_PENDING')
    bot_b_target = sum(1 for g in open_groups.values() if g.get('bot') == 'B' and g.get('status') == 'TARGET_PENDING')

    # Win rate
    wins = sum(1 for g in closed_groups if g.get('realized_pnl', 0) > 0)
    win_rate = (wins / len(closed_groups) * 100) if closed_groups else 0.0

    # Exposure (open groups with filled entries)
    filled_groups = [g for g in open_groups.values() if g.get('status') == 'TARGET_PENDING']
    long_exposure = sum(g.get('qty', 0) for g in filled_groups if g.get('entry_side') == 'BUY')
    short_exposure = sum(g.get('qty', 0) for g in filled_groups if g.get('entry_side') == 'SELL')

    return {
        'symbol': state.get('symbol', ''),
        'anchor_price': state.get('anchor_price', 0),
        'total_pnl': round(total_pnl, 2),
        'total_cycles': total_cycles,
        'open_groups': len(open_groups),
        'win_rate': round(win_rate, 1),
        'bot_a': {'entry_pending': bot_a_entry, 'target_pending': bot_a_target},
        'bot_b': {'entry_pending': bot_b_entry, 'target_pending': bot_b_target},
        'long_exposure': long_exposure,
        'short_exposure': short_exposure,
        'last_updated': state.get('last_updated', ''),
    }


def create_app(symbol: str, pair_symbol: str = "") -> Flask:
    """Create Flask app for the given symbol."""
    app = Flask(__name__)
    app.config['SYMBOL'] = symbol
    app.config['PAIR_SYMBOL'] = pair_symbol

    @app.route('/api/state')
    def api_state():
        return jsonify(_load_state(symbol))

    @app.route('/api/summary')
    def api_summary():
        state = _load_state(symbol)
        return jsonify(_compute_summary(state))

    @app.route('/')
    def index():
        return Response(_build_html(symbol, pair_symbol), mimetype='text/html')

    return app


def _build_html(symbol: str, pair_symbol: str = "") -> str:
    """Build the complete self-contained HTML dashboard."""
    pair_display = pair_symbol or "None"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TG Grid Bot — {symbol}</title>
<style>
:root {{
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
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    background: var(--bg);
    color: var(--text);
    padding: 16px;
    font-size: 13px;
}}
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 16px;
}}
.header h1 {{
    font-size: 18px;
    font-weight: 600;
}}
.header .meta {{
    color: var(--dim);
    font-size: 12px;
    text-align: right;
}}
.pulse {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--green);
    margin-right: 6px;
    animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.3; }}
}}
.kpis {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
}}
.kpi {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}}
.kpi .label {{
    color: var(--dim);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}}
.kpi .value {{
    font-size: 22px;
    font-weight: 700;
}}
.kpi .value.green {{ color: var(--green); }}
.kpi .value.red {{ color: var(--red); }}
.kpi .value.blue {{ color: var(--blue); }}
.kpi .value.orange {{ color: var(--orange); }}
.kpi .value.purple {{ color: var(--purple); }}
.bots {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
}}
.bot-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
}}
.bot-card h3 {{
    font-size: 13px;
    margin-bottom: 8px;
    color: var(--blue);
}}
.bot-card .stat {{
    display: flex;
    justify-content: space-between;
    padding: 3px 0;
    font-size: 12px;
}}
.bot-card .stat .val {{ font-weight: 600; }}
.section {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
}}
.section h2 {{
    font-size: 14px;
    margin-bottom: 12px;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}}
th {{
    text-align: left;
    padding: 6px 8px;
    border-bottom: 1px solid var(--border);
    color: var(--dim);
    font-weight: 500;
    font-size: 11px;
    text-transform: uppercase;
}}
td {{
    padding: 5px 8px;
    border-bottom: 1px solid #1e2130;
}}
tr:hover td {{ background: rgba(68, 138, 255, 0.05); }}
.pnl-pos {{ color: var(--green); font-weight: 600; }}
.pnl-neg {{ color: var(--red); font-weight: 600; }}
.status-badge {{
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
}}
.status-ENTRY_PENDING {{ background: rgba(255, 145, 0, 0.15); color: var(--orange); }}
.status-TARGET_PENDING {{ background: rgba(68, 138, 255, 0.15); color: var(--blue); }}
.status-CLOSED {{ background: rgba(0, 200, 83, 0.15); color: var(--green); }}
.chart-container {{
    height: 200px;
    position: relative;
}}
.empty-msg {{
    text-align: center;
    color: var(--dim);
    padding: 20px;
    font-style: italic;
}}
</style>
</head>
<body>

<div class="header">
    <div>
        <h1>TG Grid Bot &mdash; <span id="hdr-symbol">{symbol}</span></h1>
        <span style="color:var(--dim);font-size:12px;">
            Anchor: <span id="hdr-anchor">—</span> &nbsp;|&nbsp;
            Pair: <span id="hdr-pair">{pair_display}</span>
        </span>
    </div>
    <div class="meta">
        <span class="pulse" id="pulse"></span>LIVE<br>
        <span id="hdr-updated">—</span>
    </div>
</div>

<div class="kpis">
    <div class="kpi">
        <div class="label">Total PnL</div>
        <div class="value" id="kpi-pnl">—</div>
    </div>
    <div class="kpi">
        <div class="label">Cycles</div>
        <div class="value blue" id="kpi-cycles">—</div>
    </div>
    <div class="kpi">
        <div class="label">Open Groups</div>
        <div class="value orange" id="kpi-open">—</div>
    </div>
    <div class="kpi">
        <div class="label">Win Rate</div>
        <div class="value" id="kpi-winrate">—</div>
    </div>
    <div class="kpi">
        <div class="label">Long Exposure</div>
        <div class="value" id="kpi-long">—</div>
    </div>
    <div class="kpi">
        <div class="label">Short Exposure</div>
        <div class="value" id="kpi-short">—</div>
    </div>
</div>

<div class="bots">
    <div class="bot-card">
        <h3>Bot A (BuyBot)</h3>
        <div class="stat"><span>Entry Pending</span><span class="val" id="ba-entry">0</span></div>
        <div class="stat"><span>Target Pending</span><span class="val" id="ba-target">0</span></div>
    </div>
    <div class="bot-card">
        <h3>Bot B (SellBot)</h3>
        <div class="stat"><span>Entry Pending</span><span class="val" id="bb-entry">0</span></div>
        <div class="stat"><span>Target Pending</span><span class="val" id="bb-target">0</span></div>
    </div>
</div>

<div class="section">
    <h2>Open Positions</h2>
    <table>
        <thead>
            <tr>
                <th>Group</th>
                <th>Bot</th>
                <th>Subset</th>
                <th>Side</th>
                <th>Entry</th>
                <th>Target</th>
                <th>Qty</th>
                <th>Status</th>
                <th>Pair Order</th>
            </tr>
        </thead>
        <tbody id="open-tbody"></tbody>
    </table>
    <div class="empty-msg" id="open-empty" style="display:none;">No open positions</div>
</div>

<div class="section">
    <h2>Recent Transactions (Last 30)</h2>
    <table>
        <thead>
            <tr>
                <th>Entry ID</th>
                <th>Target ID</th>
                <th>Pair ID</th>
                <th>Bot</th>
                <th>Subset</th>
                <th>Buy @</th>
                <th>Sell @</th>
                <th>Qty</th>
                <th>PnL</th>
                <th>Closed</th>
            </tr>
        </thead>
        <tbody id="closed-tbody"></tbody>
    </table>
    <div class="empty-msg" id="closed-empty" style="display:none;">No completed trades yet</div>
</div>

<div class="section">
    <h2>Pair Trades &mdash; {pair_display}</h2>
    <div class="kpis" style="margin-bottom:12px;">
        <div class="kpi">
            <div class="label">Open Hedges</div>
            <div class="value purple" id="pair-open">0</div>
        </div>
        <div class="kpi">
            <div class="label">Completed Pairs</div>
            <div class="value blue" id="pair-closed">0</div>
        </div>
        <div class="kpi">
            <div class="label">Net Pair Qty</div>
            <div class="value" id="pair-net-qty">0</div>
        </div>
    </div>
    <table>
        <thead>
            <tr>
                <th>Pair ID</th>
                <th>Group</th>
                <th>Bot</th>
                <th>Subset</th>
                <th>Action</th>
                <th>Pair Side</th>
                <th>{pair_display} Entry</th>
                <th>Status</th>
                <th>Time</th>
            </tr>
        </thead>
        <tbody id="pair-tbody"></tbody>
    </table>
    <div class="empty-msg" id="pair-empty" style="display:none;">No pair trades yet</div>
</div>

<div class="section">
    <h2>Cumulative PnL</h2>
    <div class="chart-container">
        <canvas id="pnl-chart"></canvas>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script>
let pnlChart = null;

function fmtOid(bot, subset, groupId, role) {{
    const sign = bot === 'A' ? '-' : '+';
    return role + sign + subset + bot + '_' + groupId;
}}

function fmtPnl(v) {{
    if (v == null) return '—';
    const cls = v >= 0 ? 'pnl-pos' : 'pnl-neg';
    return '<span class="' + cls + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '</span>';
}}

function fmtTime(iso) {{
    if (!iso) return '—';
    try {{
        const d = new Date(iso);
        return d.toLocaleTimeString('en-IN', {{hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false}});
    }} catch(e) {{ return iso; }}
}}

function update() {{
    fetch('/api/state')
        .then(r => r.json())
        .then(state => {{
            if (!state || !state.symbol) return;

            // Summary
            fetch('/api/summary')
                .then(r => r.json())
                .then(s => {{
                    document.getElementById('hdr-anchor').textContent = (s.anchor_price || 0).toFixed(2);
                    document.getElementById('hdr-updated').textContent = fmtTime(s.last_updated);

                    const pnlEl = document.getElementById('kpi-pnl');
                    pnlEl.textContent = (s.total_pnl >= 0 ? '+' : '') + (s.total_pnl || 0).toFixed(2);
                    pnlEl.className = 'value ' + (s.total_pnl >= 0 ? 'green' : 'red');

                    document.getElementById('kpi-cycles').textContent = s.total_cycles || 0;
                    document.getElementById('kpi-open').textContent = s.open_groups || 0;

                    const wr = document.getElementById('kpi-winrate');
                    wr.textContent = (s.win_rate || 0).toFixed(1) + '%';
                    wr.className = 'value ' + (s.win_rate >= 50 ? 'green' : 'orange');

                    document.getElementById('kpi-long').textContent = s.long_exposure || 0;
                    document.getElementById('kpi-short').textContent = s.short_exposure || 0;

                    document.getElementById('ba-entry').textContent = s.bot_a ? s.bot_a.entry_pending : 0;
                    document.getElementById('ba-target').textContent = s.bot_a ? s.bot_a.target_pending : 0;
                    document.getElementById('bb-entry').textContent = s.bot_b ? s.bot_b.entry_pending : 0;
                    document.getElementById('bb-target').textContent = s.bot_b ? s.bot_b.target_pending : 0;
                }});

            // Open positions table
            const openGroups = state.open_groups || {{}};
            const openArr = Object.values(openGroups).sort((a,b) => {{
                if (a.bot !== b.bot) return a.bot < b.bot ? -1 : 1;
                return a.subset_index - b.subset_index;
            }});
            const openTbody = document.getElementById('open-tbody');
            const openEmpty = document.getElementById('open-empty');
            if (openArr.length === 0) {{
                openTbody.innerHTML = '';
                openEmpty.style.display = 'block';
            }} else {{
                openEmpty.style.display = 'none';
                openTbody.innerHTML = openArr.map(g => {{
                    const eid = fmtOid(g.bot, g.subset_index, g.group_id, 'EN');
                    const tid = g.status === 'TARGET_PENDING' ? fmtOid(g.bot, g.subset_index, g.group_id, 'TP') : '—';
                    const pid = g.pair_order_id ? fmtOid(g.bot, g.subset_index, g.group_id, 'PR') : '—';
                    return '<tr>' +
                        '<td title="' + g.group_id + '">' + g.group_id + '</td>' +
                        '<td>' + (g.bot === 'A' ? 'A (Buy)' : 'B (Sell)') + '</td>' +
                        '<td>' + g.subset_index + '</td>' +
                        '<td>' + g.entry_side + '</td>' +
                        '<td>' + (g.entry_fill_price || g.entry_price).toFixed(2) + '</td>' +
                        '<td>' + g.target_price.toFixed(2) + '</td>' +
                        '<td>' + g.qty + '</td>' +
                        '<td><span class="status-badge status-' + g.status + '">' + g.status.replace('_',' ') + '</span></td>' +
                        '<td style="font-size:11px;color:var(--dim);">' + pid + '</td>' +
                        '</tr>';
                }}).join('');
            }}

            // Closed trades table (last 30)
            const closed = (state.closed_groups || []).slice(-30).reverse();
            const closedTbody = document.getElementById('closed-tbody');
            const closedEmpty = document.getElementById('closed-empty');
            if (closed.length === 0) {{
                closedTbody.innerHTML = '';
                closedEmpty.style.display = 'block';
            }} else {{
                closedEmpty.style.display = 'none';
                closedTbody.innerHTML = closed.map(g => {{
                    const eid = fmtOid(g.bot, g.subset_index, g.group_id, 'EN');
                    const tid = fmtOid(g.bot, g.subset_index, g.group_id, 'TP');
                    const pid = g.pair_order_id ? fmtOid(g.bot, g.subset_index, g.group_id, 'PR') : '—';
                    const buyP = g.entry_side === 'BUY' ? (g.entry_fill_price || g.entry_price) : (g.target_fill_price || g.target_price);
                    const sellP = g.entry_side === 'SELL' ? (g.entry_fill_price || g.entry_price) : (g.target_fill_price || g.target_price);
                    return '<tr>' +
                        '<td style="font-size:11px;">' + eid + '</td>' +
                        '<td style="font-size:11px;">' + tid + '</td>' +
                        '<td style="font-size:11px;color:var(--dim);">' + pid + '</td>' +
                        '<td>' + (g.bot === 'A' ? 'A' : 'B') + '</td>' +
                        '<td>' + g.subset_index + '</td>' +
                        '<td>' + buyP.toFixed(2) + '</td>' +
                        '<td>' + sellP.toFixed(2) + '</td>' +
                        '<td>' + g.qty + '</td>' +
                        '<td>' + fmtPnl(g.realized_pnl) + '</td>' +
                        '<td>' + fmtTime(g.closed_at) + '</td>' +
                        '</tr>';
                }}).join('');
            }}

            // Pair trades section
            const pairTbody = document.getElementById('pair-tbody');
            const pairEmpty = document.getElementById('pair-empty');
            const pairRows = [];
            let openHedges = 0;
            let completedPairs = 0;
            let netPairQty = 0;

            // Open groups with pair orders (active hedges)
            openArr.forEach(g => {{
                if (g.pair_order_id && g.status === 'TARGET_PENDING') {{
                    const pid = fmtOid(g.bot, g.subset_index, g.group_id, 'PR');
                    // Bot A entry=BUY → pair=SELL; Bot B entry=SELL → pair=BUY
                    const pairSide = g.entry_side === 'BUY' ? 'SELL' : 'BUY';
                    openHedges++;
                    netPairQty += (pairSide === 'BUY' ? 1 : -1);
                    pairRows.push('<tr>' +
                        '<td style="font-size:11px;color:var(--purple);">' + pid + '</td>' +
                        '<td>' + g.group_id + '</td>' +
                        '<td>' + g.bot + '</td>' +
                        '<td>' + g.subset_index + '</td>' +
                        '<td style="color:var(--orange);">HEDGE</td>' +
                        '<td>' + pairSide + '</td>' +
                        '<td>—</td>' +
                        '<td><span class="status-badge status-TARGET_PENDING">OPEN</span></td>' +
                        '<td>' + fmtTime(g.entry_filled_at) + '</td>' +
                        '</tr>');
                }}
            }});

            // Closed groups with pair orders (unwound hedges)
            const closedWithPair = (state.closed_groups || []).filter(g => g.pair_order_id).slice(-30).reverse();
            closedWithPair.forEach(g => {{
                const pid = fmtOid(g.bot, g.subset_index, g.group_id, 'PR');
                // On target fill, pair is unwound: Bot A target=SELL → pair unwind=BUY; Bot B target=BUY → pair unwind=SELL
                const hedgeSide = g.entry_side === 'BUY' ? 'SELL' : 'BUY';
                const unwindSide = g.entry_side === 'BUY' ? 'BUY' : 'SELL';
                completedPairs++;
                // Hedge row
                pairRows.push('<tr style="opacity:0.6;">' +
                    '<td style="font-size:11px;color:var(--purple);">' + pid + '</td>' +
                    '<td>' + g.group_id + '</td>' +
                    '<td>' + g.bot + '</td>' +
                    '<td>' + g.subset_index + '</td>' +
                    '<td style="color:var(--orange);">HEDGE</td>' +
                    '<td>' + hedgeSide + '</td>' +
                    '<td>—</td>' +
                    '<td><span class="status-badge status-CLOSED">CLOSED</span></td>' +
                    '<td>' + fmtTime(g.entry_filled_at) + '</td>' +
                    '</tr>');
                // Unwind row
                pairRows.push('<tr style="opacity:0.6;">' +
                    '<td style="font-size:11px;color:var(--purple);">' + pid + '</td>' +
                    '<td>' + g.group_id + '</td>' +
                    '<td>' + g.bot + '</td>' +
                    '<td>' + g.subset_index + '</td>' +
                    '<td style="color:var(--green);">UNWIND</td>' +
                    '<td>' + unwindSide + '</td>' +
                    '<td>—</td>' +
                    '<td><span class="status-badge status-CLOSED">CLOSED</span></td>' +
                    '<td>' + fmtTime(g.target_filled_at) + '</td>' +
                    '</tr>');
            }});

            document.getElementById('pair-open').textContent = openHedges;
            document.getElementById('pair-closed').textContent = completedPairs;
            const netEl = document.getElementById('pair-net-qty');
            netEl.textContent = (netPairQty > 0 ? '+' : '') + netPairQty;
            netEl.className = 'value ' + (netPairQty === 0 ? 'green' : 'orange');

            if (pairRows.length === 0) {{
                pairTbody.innerHTML = '';
                pairEmpty.style.display = 'block';
            }} else {{
                pairEmpty.style.display = 'none';
                pairTbody.innerHTML = pairRows.join('');
            }}

            // PnL chart
            const allClosed = state.closed_groups || [];
            if (allClosed.length > 0) {{
                let cum = 0;
                const labels = [];
                const data = [];
                allClosed.forEach((g, i) => {{
                    cum += g.realized_pnl || 0;
                    labels.push(i + 1);
                    data.push(parseFloat(cum.toFixed(2)));
                }});
                const ctx = document.getElementById('pnl-chart').getContext('2d');
                if (pnlChart) pnlChart.destroy();
                pnlChart = new Chart(ctx, {{
                    type: 'line',
                    data: {{
                        labels: labels,
                        datasets: [{{
                            label: 'Cumulative PnL',
                            data: data,
                            borderColor: data[data.length-1] >= 0 ? '#00c853' : '#ff1744',
                            backgroundColor: (data[data.length-1] >= 0 ? 'rgba(0,200,83,' : 'rgba(255,23,68,') + '0.1)',
                            fill: true,
                            tension: 0.3,
                            pointRadius: 0,
                            borderWidth: 2,
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{ display: false }},
                        }},
                        scales: {{
                            x: {{
                                display: true,
                                title: {{ display: true, text: 'Trade #', color: '#888' }},
                                ticks: {{ color: '#888', maxTicksLimit: 15 }},
                                grid: {{ color: 'rgba(42,45,58,0.5)' }},
                            }},
                            y: {{
                                display: true,
                                title: {{ display: true, text: 'PnL', color: '#888' }},
                                ticks: {{ color: '#888' }},
                                grid: {{ color: 'rgba(42,45,58,0.5)' }},
                            }}
                        }}
                    }}
                }});
            }}
        }})
        .catch(err => console.error('Update failed:', err));
}}

// Initial load + 3s polling
update();
setInterval(update, 3000);
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='TG Grid Bot Dashboard')
    parser.add_argument('--symbol', required=True, help='Trading symbol (e.g., TATSILV)')
    parser.add_argument('--pair-symbol', default='', help='Pair hedge symbol (e.g., SPCENET)')
    parser.add_argument('--port', type=int, default=7777, help='Dashboard port (default: 7777)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host (default: 0.0.0.0)')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    app = create_app(args.symbol, args.pair_symbol)
    logger.info("Starting TG dashboard for %s on %s:%d", args.symbol, args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
