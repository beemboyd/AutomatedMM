"""
TG Landing Page — Unified entry point for all trading dashboards.

Serves a landing page on port 7800 and reverse-proxies all dashboards
under subpaths so external users (via Tailscale funnel) only need one URL.

Routes:
    /                       Landing page
    /tg-monitor/...         TG Grid Monitor (localhost:7777)
    /tg-config/...          TG Grid Config (localhost:7779)
    /tollgate-monitor/...   TollGate Monitor (localhost:7788)
    /tollgate-config/...    TollGate Config (localhost:7786)

Usage:
    python3 -m TG.landing                        # Start on port 7800
    python3 -m TG.landing --port 7800            # Explicit port
"""

import argparse
import logging
import requests as req
from flask import Flask, Response, request

logger = logging.getLogger(__name__)

DASHBOARDS = {
    'tg-monitor': {
        'port': 7777,
        'name': 'TG Grid Monitor',
        'desc': 'TATSILV / TATAGOLD / IDEA — live grid status, PnL, fills',
        'icon': 'chart-line',
        'color': '#00c853',
    },
    'tollgate-monitor': {
        'port': 7788,
        'name': 'TollGate Monitor',
        'desc': 'SPCENET market-making — grid levels, partial fills, PnL',
        'icon': 'toll',
        'color': '#ff9100',
    },
    'pnl-tracker': {
        'port': 9000,
        'name': 'PnL Tracker',
        'desc': 'Multi-day PnL analytics — sessions, pairs, cycles, inventory',
        'icon': 'chart-bar',
        'color': '#b388ff',
    },
}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route('/')
    def landing():
        return Response(_build_landing_html(), mimetype='text/html')

    # Proxy: dashboard root page
    @app.route('/<dashboard>/')
    @app.route('/<dashboard>')
    def proxy_page(dashboard):
        if dashboard not in DASHBOARDS:
            return 'Not found', 404
        port = DASHBOARDS[dashboard]['port']
        try:
            resp = req.get(f'http://127.0.0.1:{port}/', timeout=5)
        except req.ConnectionError:
            return Response(
                _build_offline_html(dashboard, DASHBOARDS[dashboard]),
                mimetype='text/html',
            )
        html = resp.text
        # Rewrite API paths so browser fetches go through our proxy
        html = html.replace("'/api/", f"'/{dashboard}/api/")
        html = html.replace('"/api/', f'"/{dashboard}/api/')
        # Rewrite any fetch('/') calls (unlikely but safe)
        return Response(html, mimetype='text/html')

    # Proxy: API GET/POST
    @app.route('/<dashboard>/api/<path:subpath>', methods=['GET', 'POST'])
    def proxy_api(dashboard, subpath):
        if dashboard not in DASHBOARDS:
            return 'Not found', 404
        port = DASHBOARDS[dashboard]['port']
        url = f'http://127.0.0.1:{port}/api/{subpath}'
        try:
            if request.method == 'POST':
                resp = req.post(url, json=request.get_json(), timeout=10)
            else:
                resp = req.get(url, timeout=10)
            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get('Content-Type', 'application/json'),
            )
        except req.ConnectionError:
            return Response('{"error":"Dashboard offline"}', status=502,
                            content_type='application/json')

    return app


def _build_offline_html(key: str, dash: dict) -> str:
    return f'''<!DOCTYPE html>
<html><head><title>{dash["name"]} — Offline</title>
<style>
body {{ font-family: 'JetBrains Mono', monospace; background: #0f1117; color: #e0e0e0;
       display: flex; align-items: center; justify-content: center; height: 100vh; }}
.box {{ text-align: center; padding: 40px; border: 1px solid #2a2d3a; border-radius: 12px; background: #1a1d27; }}
h2 {{ color: #ff1744; margin-bottom: 12px; }}
a {{ color: #448aff; text-decoration: none; }}
</style></head>
<body><div class="box">
<h2>{dash["name"]}</h2>
<p style="color:#888;">Dashboard on port {dash["port"]} is offline.</p>
<p style="margin-top:20px;"><a href="/">Back to Landing Page</a></p>
</div></body></html>'''


def _build_landing_html() -> str:
    # Build dashboard cards dynamically
    cards = ''
    for key, dash in DASHBOARDS.items():
        cards += f'''
        <a href="/{key}/" class="card" style="--accent:{dash['color']};" id="card-{key}">
            <div class="card-header">
                <div class="card-dot" style="background:{dash['color']};"></div>
                <span class="card-status" id="status-{key}">checking...</span>
            </div>
            <h3 style="color:{dash['color']};margin-bottom:6px;">{dash['name']}</h3>
            <p class="card-desc">{dash['desc']}</p>
            <div class="card-port">:{dash['port']}</div>
        </a>'''

    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>India-TS Trading System</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    :root {
        --bg: #0f1117;
        --card-bg: #1a1d27;
        --border: #2a2d3a;
        --text: #e0e0e0;
        --dim: #666;
        --green: #00c853;
        --red: #ff1744;
        --blue: #448aff;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        font-family: 'JetBrains Mono', 'SF Mono', 'Consolas', monospace;
        background: var(--bg);
        color: var(--text);
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 40px 20px;
    }

    /* Header */
    .header {
        text-align: center;
        margin-bottom: 48px;
    }
    .header h1 {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: 2px;
        margin-bottom: 8px;
    }
    .header .sub {
        color: var(--dim);
        font-size: 13px;
    }
    .header .pulse-bar {
        margin-top: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        font-size: 12px;
    }
    .pulse {
        display: inline-block;
        width: 8px; height: 8px;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }
    .pulse-green { background: var(--green); }
    .pulse-red { background: var(--red); }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.3; } }

    /* Grid */
    .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 20px;
        max-width: 900px;
        width: 100%;
    }

    /* Cards */
    .card {
        display: block;
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        text-decoration: none;
        color: var(--text);
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: var(--accent);
        opacity: 0;
        transition: opacity 0.2s;
    }
    .card:hover {
        border-color: var(--accent);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    .card:hover::before { opacity: 1; }
    .card-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 14px;
    }
    .card-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        animation: pulse 2s ease-in-out infinite;
    }
    .card-dot.offline {
        background: var(--red) !important;
        animation: none;
        opacity: 0.5;
    }
    .card-status {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--dim);
    }
    .card-status.online { color: var(--green); }
    .card-status.offline { color: var(--red); }
    .card h3 {
        font-size: 15px;
        font-weight: 600;
    }
    .card-desc {
        font-size: 11px;
        color: var(--dim);
        line-height: 1.5;
        margin-bottom: 12px;
    }
    .card-port {
        font-size: 10px;
        color: var(--dim);
        opacity: 0.5;
    }

    /* Footer */
    .footer {
        margin-top: 48px;
        text-align: center;
        color: var(--dim);
        font-size: 11px;
        line-height: 1.6;
    }

    /* Summary bar */
    .summary {
        max-width: 900px;
        width: 100%;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 12px;
        margin-bottom: 32px;
    }
    .summary-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .summary-label {
        font-size: 10px;
        text-transform: uppercase;
        color: var(--dim);
        margin-bottom: 4px;
    }
    .summary-value {
        font-size: 16px;
        font-weight: 700;
    }
    .pnl-pos { color: var(--green); }
    .pnl-neg { color: var(--red); }
</style>
</head>
<body>

<div class="header">
    <h1>INDIA-TS</h1>
    <div class="sub">Trading System Dashboard</div>
    <div class="pulse-bar">
        <span class="pulse pulse-green" id="master-pulse"></span>
        <span id="master-status" style="color:var(--dim);">Checking systems...</span>
    </div>
</div>

<!-- LIVE SUMMARY -->
<div class="summary" id="summary-bar">
    <div class="summary-card">
        <div class="summary-label">TG PnL</div>
        <div class="summary-value" id="sum-tg-pnl">—</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">TG Cycles</div>
        <div class="summary-value" style="color:var(--blue);" id="sum-tg-cycles">—</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">TollGate PnL</div>
        <div class="summary-value" id="sum-tg2-pnl">—</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">TollGate Cycles</div>
        <div class="summary-value" style="color:var(--blue);" id="sum-tg2-cycles">—</div>
    </div>
    <div class="summary-card">
        <div class="summary-label">TollGate Inv</div>
        <div class="summary-value" id="sum-tg2-inv">—</div>
    </div>
</div>

<!-- DASHBOARD CARDS -->
<div class="grid">''' + cards + '''
</div>

<div class="footer">
    India-TS Trading System<br>
    <span id="footer-time"></span>
</div>

<script>
const DASHBOARDS = ''' + _dashboards_json() + ''';

function fmtPnl(v, el) {
    if (v == null || isNaN(v)) { el.textContent = '—'; el.className = 'summary-value'; return; }
    el.textContent = (v >= 0 ? '+' : '') + v.toFixed(2);
    el.className = 'summary-value ' + (v >= 0 ? 'pnl-pos' : 'pnl-neg');
}

function checkDashboards() {
    let onlineCount = 0;
    const total = Object.keys(DASHBOARDS).length;

    Object.entries(DASHBOARDS).forEach(([key, dash]) => {
        fetch('/' + key + '/api/state', {signal: AbortSignal.timeout(3000)})
            .then(r => {
                if (!r.ok) throw new Error('not ok');
                return r.json();
            })
            .then(data => {
                onlineCount++;
                const dot = document.querySelector('#card-' + key + ' .card-dot');
                const status = document.getElementById('status-' + key);
                dot.classList.remove('offline');
                status.textContent = 'online';
                status.className = 'card-status online';

                // Extract summary data
                const summary = data.summary || {};
                if (key === 'tg-monitor') {
                    // TG has multiple symbols — aggregate if available
                    const allState = data.all_state || {};
                    let totalPnl = 0, totalCycles = 0;
                    if (Object.keys(allState).length > 0) {
                        Object.values(allState).forEach(s => {
                            totalPnl += (s.total_pnl || 0);
                            totalCycles += (s.total_cycles || 0);
                        });
                    } else {
                        totalPnl = summary.total_pnl || 0;
                        totalCycles = summary.total_cycles || 0;
                    }
                    fmtPnl(totalPnl, document.getElementById('sum-tg-pnl'));
                    document.getElementById('sum-tg-cycles').textContent = totalCycles;
                }
                if (key === 'tollgate-monitor') {
                    fmtPnl(summary.total_pnl || 0, document.getElementById('sum-tg2-pnl'));
                    document.getElementById('sum-tg2-cycles').textContent = summary.total_cycles || 0;
                    const inv = summary.net_inventory || 0;
                    const invEl = document.getElementById('sum-tg2-inv');
                    invEl.textContent = (inv >= 0 ? '+' : '') + inv;
                    invEl.className = 'summary-value ' + (inv === 0 ? '' : inv > 0 ? 'pnl-pos' : 'pnl-neg');
                }

                updateMaster(onlineCount, total);
            })
            .catch(() => {
                const dot = document.querySelector('#card-' + key + ' .card-dot');
                const status = document.getElementById('status-' + key);
                dot.classList.add('offline');
                status.textContent = 'offline';
                status.className = 'card-status offline';
                updateMaster(onlineCount, total);
            });
    });
}

function updateMaster(online, total) {
    const pulse = document.getElementById('master-pulse');
    const text = document.getElementById('master-status');
    if (online === total) {
        pulse.className = 'pulse pulse-green';
        text.textContent = 'All systems online';
        text.style.color = 'var(--green)';
    } else if (online > 0) {
        pulse.className = 'pulse pulse-green';
        text.textContent = online + '/' + total + ' systems online';
        text.style.color = 'var(--dim)';
    } else {
        pulse.className = 'pulse pulse-red';
        text.textContent = 'Systems offline';
        text.style.color = 'var(--red)';
    }
}

function updateTime() {
    document.getElementById('footer-time').textContent =
        new Date().toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            dateStyle: 'medium',
            timeStyle: 'medium',
            hour12: false
        });
}

checkDashboards();
updateTime();
setInterval(checkDashboards, 5000);
setInterval(updateTime, 1000);
</script>
</body>
</html>'''


def _dashboards_json() -> str:
    import json
    return json.dumps({k: {'port': v['port'], 'name': v['name']} for k, v in DASHBOARDS.items()})


def main():
    parser = argparse.ArgumentParser(description='India-TS Landing Page')
    parser.add_argument('--port', type=int, default=7800, help='Port (default: 7800)')
    parser.add_argument('--host', default='0.0.0.0', help='Bind host')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
    )

    app = create_app()
    logger.info("Starting India-TS Landing Page on %s:%d", args.host, args.port)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == '__main__':
    main()
