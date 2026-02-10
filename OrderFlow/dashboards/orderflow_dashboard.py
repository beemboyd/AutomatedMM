#!/usr/bin/env python3
"""
OrderFlow Real-Time Dashboard
Flask app serving live order flow metrics from PostgreSQL of_metrics table.
Port: 3009 | Auto-refresh: 10s
"""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
import pytz
from flask import Flask, jsonify, render_template_string, request

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PORT = 3009
IST = pytz.timezone("Asia/Kolkata")
BASE_DIR = Path(__file__).resolve().parent.parent  # OrderFlow/
CONFIG_PATH = BASE_DIR / "config" / "orderflow_config.json"
LOG_DIR = Path("/Users/maverick/PycharmProjects/India-TS/Daily/logs/orderflow")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"dashboard_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def load_db_config():
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    db = cfg["db"]
    return {
        "host": db["host"],
        "port": db["port"],
        "dbname": db["name"],
        "user": db["user"],
        "password": db.get("password", ""),
    }


DB_CFG = load_db_config()


def get_conn():
    return psycopg2.connect(**DB_CFG)


def query_rows(sql, params=None):
    """Return list[dict] for a SELECT query."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_one(sql, params=None):
    rows = query_rows(sql, params)
    return rows[0] if rows else None


def compute_ema(values, period):
    """Compute EMA matching PineScript ta.ema()."""
    if not values:
        return []
    k = 2.0 / (period + 1)
    ema = [values[0]]
    for i in range(1, len(values)):
        ema.append(values[i] * k + ema[-1] * (1 - k))
    return ema

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/symbols")
def api_symbols():
    rows = query_rows("SELECT DISTINCT symbol FROM of_metrics ORDER BY symbol")
    return jsonify([r["symbol"] for r in rows])


@app.route("/api/latest")
def api_latest():
    symbol = request.args.get("symbol", "MTARTECH")
    row = query_one(
        "SELECT * FROM of_metrics WHERE symbol=%s ORDER BY ts DESC LIMIT 1",
        (symbol,),
    )
    if not row:
        return jsonify({"error": "no data"}), 404
    # Convert datetime to IST string
    if row.get("ts"):
        row["ts_ist"] = row["ts"].astimezone(IST).strftime("%H:%M:%S")
        row["ts_iso"] = row["ts"].astimezone(IST).isoformat()
    # Make all values JSON-serialisable
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.isoformat()
    return jsonify(row)


@app.route("/api/timeline")
def api_timeline():
    symbol = request.args.get("symbol", "MTARTECH")
    minutes = int(request.args.get("minutes", 60))
    cutoff = datetime.now(pytz.utc) - timedelta(minutes=minutes)

    rows = query_rows(
        """SELECT ts, price_close, cumulative_delta, trade_delta,
                  buying_pressure, selling_pressure,
                  bid_ask_ratio, divergence_score, cvd_slope,
                  phase, phase_confidence, interval_volume,
                  price_open, price_high, price_low, vwap
           FROM of_metrics
           WHERE symbol=%s AND ts >= %s
           ORDER BY ts ASC""",
        (symbol, cutoff),
    )

    def _v(r, k):
        v = r.get(k)
        return float(v) if v is not None else None

    # Delta CVD (PineScript candle-direction logic):
    #   close > open → +volume, close < open → -volume, equal → 0
    delta_cvd = []
    for r in rows:
        pc, po, vol = _v(r, "price_close"), _v(r, "price_open"), _v(r, "interval_volume")
        if pc is not None and po is not None and vol is not None:
            if pc > po:
                delta_cvd.append(vol)
            elif pc < po:
                delta_cvd.append(-vol)
            else:
                delta_cvd.append(0.0)
        else:
            delta_cvd.append(0.0)

    dcvd_ema21 = compute_ema(delta_cvd, 21)
    dcvd_ema50 = compute_ema(delta_cvd, 50)

    return jsonify(
        {
            "ts": [r["ts"].astimezone(IST).strftime("%H:%M:%S") for r in rows],
            "price_close": [_v(r, "price_close") for r in rows],
            "cumulative_delta": [_v(r, "cumulative_delta") for r in rows],
            "trade_delta": [_v(r, "trade_delta") for r in rows],
            "buying_pressure": [_v(r, "buying_pressure") for r in rows],
            "selling_pressure": [_v(r, "selling_pressure") for r in rows],
            "bid_ask_ratio": [_v(r, "bid_ask_ratio") for r in rows],
            "divergence_score": [_v(r, "divergence_score") for r in rows],
            "cvd_slope": [_v(r, "cvd_slope") for r in rows],
            "phase": [r.get("phase", "unknown") for r in rows],
            "phase_confidence": [_v(r, "phase_confidence") for r in rows],
            "interval_volume": [_v(r, "interval_volume") for r in rows],
            "vwap": [_v(r, "vwap") for r in rows],
            "delta_cvd": [round(v, 2) for v in delta_cvd],
            "dcvd_ema21": [round(v, 2) for v in dcvd_ema21],
            "dcvd_ema50": [round(v, 2) for v in dcvd_ema50],
        }
    )


@app.route("/api/events")
def api_events():
    symbol = request.args.get("symbol", "MTARTECH")
    minutes = int(request.args.get("minutes", 120))
    cutoff = datetime.now(pytz.utc) - timedelta(minutes=minutes)

    # Phase transitions – where phase changed from prior row
    phase_sql = """
        WITH lagged AS (
            SELECT ts, phase, phase_confidence,
                   LAG(phase) OVER (ORDER BY ts) AS prev_phase
            FROM of_metrics WHERE symbol=%s AND ts >= %s
        )
        SELECT ts, phase, phase_confidence, prev_phase
        FROM lagged
        WHERE phase != prev_phase AND prev_phase IS NOT NULL
        ORDER BY ts DESC LIMIT 20
    """
    phases = query_rows(phase_sql, (symbol, cutoff))

    # Absorption events
    absorption_sql = """
        SELECT ts, absorption_buy, absorption_sell, price_close, trade_delta
        FROM of_metrics
        WHERE symbol=%s AND ts >= %s AND (absorption_buy=true OR absorption_sell=true)
        ORDER BY ts DESC LIMIT 20
    """
    absorptions = query_rows(absorption_sql, (symbol, cutoff))

    # Large trades
    large_sql = """
        SELECT ts, large_trade_count, large_trade_volume, price_close, trade_delta
        FROM of_metrics
        WHERE symbol=%s AND ts >= %s AND large_trade_count > 0
        ORDER BY ts DESC LIMIT 20
    """
    large = query_rows(large_sql, (symbol, cutoff))

    def _fmt(rows):
        for r in rows:
            if r.get("ts"):
                r["ts_ist"] = r["ts"].astimezone(IST).strftime("%H:%M:%S")
                r["ts"] = r["ts"].isoformat()
            for k, v in list(r.items()):
                if isinstance(v, datetime):
                    r[k] = v.isoformat()
        return rows

    return jsonify(
        {
            "phase_transitions": _fmt(phases),
            "absorptions": _fmt(absorptions),
            "large_trades": _fmt(large),
        }
    )


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OrderFlow Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
     background:#0a0a0f;color:#e0e0e0;min-height:100vh}
a{color:#3b82f6;text-decoration:none}

/* Header */
.header{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);
        padding:14px 24px;display:flex;align-items:center;gap:18px;
        border-bottom:1px solid #1e293b;flex-wrap:wrap}
.header h1{font-size:1.15rem;color:#e2e8f0;white-space:nowrap}
.header select{background:#1e293b;color:#e2e8f0;border:1px solid #334155;
               border-radius:6px;padding:6px 10px;font-size:.85rem}
.price-block{display:flex;align-items:baseline;gap:8px}
.price-val{font-size:1.3rem;font-weight:700;color:#f8fafc}
.price-chg{font-size:.85rem;font-weight:600}
.phase-badge{padding:4px 12px;border-radius:12px;font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.phase-accumulation{background:#0d9488;color:#f0fdfa}
.phase-markup{background:#16a34a;color:#f0fdf4}
.phase-distribution{background:#d97706;color:#fffbeb}
.phase-markdown{background:#dc2626;color:#fef2f2}
.phase-unknown{background:#475569;color:#f1f5f9}
.confidence-text{font-size:.75rem;color:#94a3b8}
.last-update{margin-left:auto;font-size:.75rem;color:#64748b;white-space:nowrap}

/* Lookback buttons */
.controls{padding:10px 24px;display:flex;gap:8px;align-items:center;background:#0f1117;border-bottom:1px solid #1e293b}
.controls span{font-size:.8rem;color:#64748b;margin-right:4px}
.lb-btn{background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:6px;padding:5px 14px;cursor:pointer;font-size:.78rem;transition:all .2s}
.lb-btn:hover{background:#334155;color:#e2e8f0}
.lb-btn.active{background:#3b82f6;color:#fff;border-color:#3b82f6}

/* Stat cards row */
.stats{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;padding:14px 24px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}}
.stat-card{background:#111827;border:1px solid #1e293b;border-radius:10px;padding:14px 16px;text-align:center}
.stat-label{font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;color:#64748b;margin-bottom:6px}
.stat-value{font-size:1.5rem;font-weight:700}
.stat-sub{font-size:.7rem;color:#64748b;margin-top:4px}

/* Chart grid */
.charts{display:grid;grid-template-columns:1fr 1fr;gap:14px;padding:0 24px 14px}
@media(max-width:900px){.charts{grid-template-columns:1fr}}
.chart-card{background:#111827;border:1px solid #1e293b;border-radius:10px;padding:14px;position:relative;height:300px}
.chart-card h3{font-size:.8rem;color:#94a3b8;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}
.chart-card canvas{width:100%!important;height:calc(100% - 28px)!important}

/* Event log */
.events{padding:0 24px 24px}
.events-card{background:#111827;border:1px solid #1e293b;border-radius:10px;padding:16px;max-height:280px;overflow-y:auto}
.events-card h3{font-size:.85rem;color:#94a3b8;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}
.ev-table{width:100%;border-collapse:collapse;font-size:.78rem}
.ev-table th{text-align:left;padding:6px 8px;color:#64748b;border-bottom:1px solid #1e293b;font-weight:600}
.ev-table td{padding:6px 8px;border-bottom:1px solid #0f172a}
.ev-phase{color:#0d9488}.ev-absorb{color:#d97706}.ev-large{color:#8b5cf6}

/* Scrollbar */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:#0a0a0f}
::-webkit-scrollbar-thumb{background:#334155;border-radius:3px}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
    <h1>OrderFlow</h1>
    <select id="symbolSelect"></select>
    <div class="price-block">
        <span class="price-val" id="hdrPrice">--</span>
        <span class="price-chg" id="hdrChg">--</span>
    </div>
    <span class="phase-badge phase-unknown" id="hdrPhase">--</span>
    <span class="confidence-text" id="hdrConf"></span>
    <span class="last-update" id="hdrTime">--</span>
</div>

<!-- Lookback controls -->
<div class="controls">
    <span>Lookback:</span>
    <button class="lb-btn" data-min="30">30m</button>
    <button class="lb-btn active" data-min="60">1hr</button>
    <button class="lb-btn" data-min="120">2hr</button>
    <button class="lb-btn" data-min="390">Full Day</button>
</div>

<!-- Stat cards -->
<div class="stats">
    <div class="stat-card">
        <div class="stat-label">Buying Pressure</div>
        <div class="stat-value" id="sBuy" style="color:#10b981">--</div>
        <div class="stat-sub">0-100</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Selling Pressure</div>
        <div class="stat-value" id="sSell" style="color:#ef4444">--</div>
        <div class="stat-sub">0-100</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Bid / Ask Ratio</div>
        <div class="stat-value" id="sBar">--</div>
        <div class="stat-sub" id="sBarSub">&gt;1 bullish</div>
    </div>
    <div class="stat-card">
        <div class="stat-label">CVD Slope</div>
        <div class="stat-value" id="sCvd">--</div>
        <div class="stat-sub" id="sCvdDir"></div>
    </div>
    <div class="stat-card">
        <div class="stat-label">Divergence Score</div>
        <div class="stat-value" id="sDiv">--</div>
        <div class="stat-sub">-100 to +100</div>
    </div>
</div>

<!-- Charts -->
<div class="charts">
    <div class="chart-card"><h3>Price + CVD</h3><canvas id="chartPriceCvd"></canvas></div>
    <div class="chart-card"><h3>Buying vs Selling Pressure</h3><canvas id="chartPressure"></canvas></div>
    <div class="chart-card"><h3>Trade Delta</h3><canvas id="chartDelta"></canvas></div>
    <div class="chart-card"><h3>Bid/Ask Ratio + Divergence</h3><canvas id="chartRatioDiv"></canvas></div>
    <div class="chart-card" style="grid-column:1/-1"><h3>Delta CVD — EMA(21) vs EMA(50)</h3><canvas id="chartDeltaCvd"></canvas></div>
</div>

<!-- Event log -->
<div class="events">
    <div class="events-card">
        <h3>Event Log</h3>
        <table class="ev-table">
            <thead><tr><th>Time</th><th>Type</th><th>Detail</th></tr></thead>
            <tbody id="evBody"></tbody>
        </table>
    </div>
</div>

<script>
// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentSymbol = 'MTARTECH';
let lookbackMin = 60;
let charts = {};

// ---------------------------------------------------------------------------
// Colour helpers
// ---------------------------------------------------------------------------
const phaseColors = {accumulation:'#0d9488',markup:'#16a34a',distribution:'#d97706',markdown:'#dc2626',unknown:'#475569'};
function phaseClass(p){return 'phase-'+(p||'unknown');}

// ---------------------------------------------------------------------------
// Init charts (Chart.js 4)
// ---------------------------------------------------------------------------
function initCharts(){
    const gridColor = '#1e293b';
    const tickColor = '#64748b';
    const baseOpts = {responsive:true,maintainAspectRatio:false,animation:{duration:0},
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{labels:{color:'#94a3b8',boxWidth:12,font:{size:11}}},tooltip:{mode:'index',intersect:false}},
    };

    // 1) Price + CVD (dual Y)
    charts.priceCvd = new Chart(document.getElementById('chartPriceCvd'),{
        type:'line',
        data:{labels:[],datasets:[
            {label:'Price',data:[],borderColor:'#3b82f6',backgroundColor:'rgba(59,130,246,0.08)',
             borderWidth:1.5,pointRadius:0,tension:0.3,yAxisID:'y',fill:true},
            {label:'CVD',data:[],borderColor:'#f59e0b',backgroundColor:'rgba(245,158,11,0.08)',
             borderWidth:1.5,pointRadius:0,tension:0.3,yAxisID:'y1',fill:false},
        ]},
        options:{...baseOpts,scales:{
            x:{ticks:{color:tickColor,maxTicksLimit:12,font:{size:10}},grid:{color:gridColor}},
            y:{position:'left',ticks:{color:'#3b82f6',font:{size:10}},grid:{color:gridColor},title:{display:true,text:'Price',color:'#3b82f6',font:{size:10}}},
            y1:{position:'right',ticks:{color:'#f59e0b',font:{size:10}},grid:{drawOnChartArea:false},title:{display:true,text:'CVD',color:'#f59e0b',font:{size:10}}},
        }}
    });

    // 2) Pressure
    charts.pressure = new Chart(document.getElementById('chartPressure'),{
        type:'line',
        data:{labels:[],datasets:[
            {label:'Buying',data:[],borderColor:'#10b981',backgroundColor:'rgba(16,185,129,0.15)',
             borderWidth:1.5,pointRadius:0,tension:0.3,fill:true},
            {label:'Selling',data:[],borderColor:'#ef4444',backgroundColor:'rgba(239,68,68,0.15)',
             borderWidth:1.5,pointRadius:0,tension:0.3,fill:true},
        ]},
        options:{...baseOpts,scales:{
            x:{ticks:{color:tickColor,maxTicksLimit:12,font:{size:10}},grid:{color:gridColor}},
            y:{min:0,max:100,ticks:{color:tickColor,font:{size:10}},grid:{color:gridColor}},
        }}
    });

    // 3) Delta bars
    charts.delta = new Chart(document.getElementById('chartDelta'),{
        type:'bar',
        data:{labels:[],datasets:[{
            label:'Trade Delta',data:[],
            backgroundColor:[],borderWidth:0,barPercentage:0.85,
        }]},
        options:{...baseOpts,scales:{
            x:{ticks:{color:tickColor,maxTicksLimit:12,font:{size:10}},grid:{color:gridColor}},
            y:{ticks:{color:tickColor,font:{size:10}},grid:{color:gridColor}},
        },plugins:{...baseOpts.plugins,legend:{display:false}}}
    });

    // 4) Ratio + Divergence (dual Y)
    charts.ratioDiv = new Chart(document.getElementById('chartRatioDiv'),{
        type:'line',
        data:{labels:[],datasets:[
            {label:'Bid/Ask Ratio',data:[],borderColor:'#8b5cf6',
             borderWidth:1.5,pointRadius:0,tension:0.3,yAxisID:'y',fill:false},
            {label:'Divergence',data:[],borderColor:'#ec4899',
             borderWidth:1.5,pointRadius:0,tension:0.3,yAxisID:'y1',fill:false},
        ]},
        options:{...baseOpts,scales:{
            x:{ticks:{color:tickColor,maxTicksLimit:12,font:{size:10}},grid:{color:gridColor}},
            y:{position:'left',ticks:{color:'#8b5cf6',font:{size:10}},grid:{color:gridColor},
               title:{display:true,text:'Ratio',color:'#8b5cf6',font:{size:10}}},
            y1:{position:'right',ticks:{color:'#ec4899',font:{size:10}},grid:{drawOnChartArea:false},
                title:{display:true,text:'Divergence',color:'#ec4899',font:{size:10}}},
        },plugins:{...baseOpts.plugins,
            annotation:{annotations:{refLine:{type:'line',yMin:1,yMax:1,borderColor:'rgba(139,92,246,0.3)',borderDash:[4,4],borderWidth:1,yScaleID:'y'}}}
        }}
    });

    // 5) Delta CVD EMA(21) vs EMA(50) + zero line
    charts.deltaCvd = new Chart(document.getElementById('chartDeltaCvd'),{
        type:'line',
        data:{labels:[],datasets:[
            {label:'ΔCVD EMA(21)',data:[],borderColor:'#10b981',
             borderWidth:2,pointRadius:0,tension:0.3,fill:false},
            {label:'ΔCVD EMA(50)',data:[],borderColor:'#ef4444',
             borderWidth:2,pointRadius:0,tension:0.3,fill:false},
        ]},
        options:{...baseOpts,scales:{
            x:{ticks:{color:tickColor,maxTicksLimit:20,font:{size:10}},grid:{color:gridColor}},
            y:{ticks:{color:tickColor,font:{size:10}},grid:{color:gridColor}},
        },plugins:{...baseOpts.plugins,
            annotation:{annotations:{zeroLine:{type:'line',yMin:0,yMax:0,borderColor:'#475569',borderWidth:1,borderDash:[4,4]}}}
        }}
    });
}

// ---------------------------------------------------------------------------
// Data fetch
// ---------------------------------------------------------------------------
async function fetchLatest(){
    try{
        const r = await fetch(`/api/latest?symbol=${currentSymbol}`);
        if(!r.ok) return;
        const d = await r.json();

        // Header
        const price = d.price_close!=null ? parseFloat(d.price_close).toFixed(2) : '--';
        document.getElementById('hdrPrice').textContent = price;

        const open = d.price_open!=null ? parseFloat(d.price_open) : null;
        const close = d.price_close!=null ? parseFloat(d.price_close) : null;
        const chgEl = document.getElementById('hdrChg');
        if(open && close){
            const chg = close - open;
            const pct = ((chg/open)*100).toFixed(2);
            chgEl.textContent = `${chg>=0?'+':''}${chg.toFixed(2)} (${chg>=0?'+':''}${pct}%)`;
            chgEl.style.color = chg>=0 ? '#10b981' : '#ef4444';
        }

        const phase = d.phase || 'unknown';
        const phEl = document.getElementById('hdrPhase');
        phEl.textContent = phase;
        phEl.className = 'phase-badge ' + phaseClass(phase);

        const conf = d.phase_confidence!=null ? (parseFloat(d.phase_confidence)*100).toFixed(0) : '--';
        document.getElementById('hdrConf').textContent = conf+'% confidence';
        document.getElementById('hdrTime').textContent = d.ts_ist ? `Last: ${d.ts_ist} IST` : '--';

        // Stat cards
        const bp = d.buying_pressure!=null ? parseFloat(d.buying_pressure).toFixed(0) : '--';
        const sp = d.selling_pressure!=null ? parseFloat(d.selling_pressure).toFixed(0) : '--';
        document.getElementById('sBuy').textContent = bp;
        document.getElementById('sSell').textContent = sp;

        const bar = d.bid_ask_ratio!=null ? parseFloat(d.bid_ask_ratio).toFixed(2) : '--';
        const barEl = document.getElementById('sBar');
        barEl.textContent = bar;
        barEl.style.color = bar!='--' ? (parseFloat(bar)>=1?'#10b981':'#ef4444') : '#e0e0e0';

        const cvd = d.cvd_slope!=null ? parseFloat(d.cvd_slope).toFixed(1) : '--';
        const cvdEl = document.getElementById('sCvd');
        cvdEl.textContent = cvd;
        if(cvd!='--'){
            const v = parseFloat(cvd);
            cvdEl.style.color = v>0?'#10b981':v<0?'#ef4444':'#94a3b8';
            document.getElementById('sCvdDir').textContent = v>0?'Accelerating':'Decelerating';
        }

        const div = d.divergence_score!=null ? parseFloat(d.divergence_score).toFixed(0) : '--';
        const divEl = document.getElementById('sDiv');
        divEl.textContent = div;
        if(div!='--'){
            const v = parseFloat(div);
            divEl.style.color = v>20?'#ef4444':v<-20?'#10b981':'#94a3b8';
        }
    }catch(e){console.error('fetchLatest',e)}
}

async function fetchTimeline(){
    try{
        const r = await fetch(`/api/timeline?symbol=${currentSymbol}&minutes=${lookbackMin}`);
        if(!r.ok) return;
        const d = await r.json();
        const ts = d.ts || [];

        // Price + CVD
        charts.priceCvd.data.labels = ts;
        charts.priceCvd.data.datasets[0].data = d.price_close;
        charts.priceCvd.data.datasets[1].data = d.cumulative_delta;
        charts.priceCvd.update('none');

        // Pressure
        charts.pressure.data.labels = ts;
        charts.pressure.data.datasets[0].data = d.buying_pressure;
        charts.pressure.data.datasets[1].data = d.selling_pressure;
        charts.pressure.update('none');

        // Delta bars
        const colors = (d.trade_delta||[]).map(v=>v>=0?'rgba(16,185,129,0.7)':'rgba(239,68,68,0.7)');
        charts.delta.data.labels = ts;
        charts.delta.data.datasets[0].data = d.trade_delta;
        charts.delta.data.datasets[0].backgroundColor = colors;
        charts.delta.update('none');

        // Ratio + Divergence
        charts.ratioDiv.data.labels = ts;
        charts.ratioDiv.data.datasets[0].data = d.bid_ask_ratio;
        charts.ratioDiv.data.datasets[1].data = d.divergence_score;
        charts.ratioDiv.update('none');

        // Delta CVD EMAs
        charts.deltaCvd.data.labels = ts;
        charts.deltaCvd.data.datasets[0].data = d.dcvd_ema21;
        charts.deltaCvd.data.datasets[1].data = d.dcvd_ema50;
        charts.deltaCvd.update('none');
    }catch(e){console.error('fetchTimeline',e)}
}

async function fetchEvents(){
    try{
        const r = await fetch(`/api/events?symbol=${currentSymbol}&minutes=${lookbackMin*2}`);
        if(!r.ok) return;
        const d = await r.json();
        const tbody = document.getElementById('evBody');
        let html = '';

        // Phase transitions
        (d.phase_transitions||[]).forEach(e=>{
            html+=`<tr><td>${e.ts_ist}</td><td class="ev-phase">Phase</td>
                   <td>${e.prev_phase} &rarr; <strong>${e.phase}</strong> (${(parseFloat(e.phase_confidence)*100).toFixed(0)}%)</td></tr>`;
        });
        // Absorptions
        (d.absorptions||[]).forEach(e=>{
            const type = e.absorption_buy ? 'Buy Absorption' : 'Sell Absorption';
            html+=`<tr><td>${e.ts_ist}</td><td class="ev-absorb">Absorb</td>
                   <td>${type} @ ${parseFloat(e.price_close).toFixed(2)} | delta=${parseFloat(e.trade_delta).toFixed(0)}</td></tr>`;
        });
        // Large trades
        (d.large_trades||[]).forEach(e=>{
            html+=`<tr><td>${e.ts_ist}</td><td class="ev-large">Large</td>
                   <td>${e.large_trade_count} trades, vol=${e.large_trade_volume} @ ${parseFloat(e.price_close).toFixed(2)}</td></tr>`;
        });

        tbody.innerHTML = html || '<tr><td colspan="3" style="color:#475569">No events</td></tr>';
    }catch(e){console.error('fetchEvents',e)}
}

async function fetchSymbols(){
    try{
        const r = await fetch('/api/symbols');
        if(!r.ok) return;
        const syms = await r.json();
        const sel = document.getElementById('symbolSelect');
        sel.innerHTML = '';
        syms.forEach(s=>{
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            if(s===currentSymbol) opt.selected = true;
            sel.appendChild(opt);
        });
    }catch(e){console.error('fetchSymbols',e)}
}

function refreshAll(){
    fetchLatest();
    fetchTimeline();
    fetchEvents();
}

// ---------------------------------------------------------------------------
// Event bindings
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded',()=>{
    initCharts();
    fetchSymbols();
    refreshAll();
    setInterval(refreshAll, 10000);

    // Symbol change
    document.getElementById('symbolSelect').addEventListener('change',e=>{
        currentSymbol = e.target.value;
        refreshAll();
    });

    // Lookback buttons
    document.querySelectorAll('.lb-btn').forEach(btn=>{
        btn.addEventListener('click',()=>{
            document.querySelectorAll('.lb-btn').forEach(b=>b.classList.remove('active'));
            btn.classList.add('active');
            lookbackMin = parseInt(btn.dataset.min);
            refreshAll();
        });
    });
});
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting OrderFlow Dashboard on port %d", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=False)
