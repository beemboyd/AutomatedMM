# Market Regime & Momentum Dashboards Documentation

**Created:** 2025-12-08
**Author:** Claude
**Purpose:** Documentation of Market Regime Dashboard (port 8080) and Unified Market Momentum Dashboard (port 8504)

---

## Table of Contents

1. [Dashboard Overview](#dashboard-overview)
2. [Market Regime Dashboard (Port 8080)](#market-regime-dashboard-port-8080)
3. [Unified Market Momentum Dashboard (Port 8504)](#unified-market-momentum-dashboard-port-8504)
4. [How to Start the Dashboards](#how-to-start-the-dashboards)
5. [Key Metrics Explained](#key-metrics-explained)
6. [Data Sources](#data-sources)
7. [API Endpoints](#api-endpoints)

---

## Dashboard Overview

| Dashboard | Port | Technology | Purpose |
|-----------|------|------------|---------|
| **Market Regime** | 8080 | Flask | Real-time regime analysis, Kelly Criterion, SMA breadth |
| **Unified Momentum** | 8504 | Streamlit | Daily & hourly breadth analysis, Fast/Slow WM trends |

---

## Market Regime Dashboard (Port 8080)

### File Location
`/Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py`

### URL
http://localhost:8080

### Purpose
Comprehensive real-time market regime analysis with ML insights, position sizing recommendations, and multi-timeframe analysis.

### Key Sections

#### 1. Current Market Regime
Displays the current market state based on trend analysis:

| Regime | Color | Description |
|--------|-------|-------------|
| **Strong Uptrend** | Dark Green | Strong bullish momentum, high confidence longs |
| **Uptrend** | Light Green | Bullish bias, favor long positions |
| **Choppy Bullish** | Yellow | Mixed with bullish lean |
| **Choppy** | Gray | No clear direction, reduce position size |
| **Choppy Bearish** | Orange | Mixed with bearish lean |
| **Downtrend** | Light Red | Bearish bias, favor short positions |
| **Strong Downtrend** | Dark Red | Strong bearish momentum, high confidence shorts |

#### 2. Kelly Criterion Position Sizing
Calculates optimal position sizing based on:

```
Kelly Formula: f* = (p × b - q) / b

Where:
- p = Win probability (from historical regime performance)
- q = Loss probability (1 - p)
- b = Win/Loss ratio (average win / average loss)
```

**Displayed Metrics:**
- **Kelly %**: Recommended position size percentage
- **Expected Value**: Expected return per trade
- **Win Probability**: Historical win rate for current regime
- **Win/Loss Ratio**: Average winning trade / Average losing trade
- **Max Positions**: Recommended number of concurrent positions
- **Stop Loss %**: Recommended stop loss percentage
- **Preferred Direction**: LONG, SHORT, or NEUTRAL

#### 3. Market Score Indicators
Three key scores displayed with sparklines:

| Score | Range | Description |
|-------|-------|-------------|
| **Market Score** | -1 to +1 | Overall market direction composite |
| **Trend Score** | -1 to +1 | Strength and direction of trend |
| **Volatility Score** | 0 to 1 | Current market volatility level |

#### 4. SMA Breadth Analysis
Tracks percentage of stocks above key moving averages:

- **SMA20 Breadth**: % of stocks above 20-day SMA
- **SMA50 Breadth**: % of stocks above 50-day SMA
- **5-Day Trend**: Direction and magnitude of change
- **20-Day Trend**: Longer-term breadth direction

**Interpretation:**
| SMA20 Breadth | Market State |
|---------------|--------------|
| > 65% | Strong Uptrend |
| 50-65% | Uptrend |
| 40-50% | Neutral/Choppy |
| < 40% | Downtrend |

#### 5. Volume Breadth Analysis
Tracks volume participation:

- **Volume Breadth**: % of stocks with above-average volume
- **Volume Participation**: Strength of volume in trending stocks

#### 6. G Pattern Tracker
Monitors G Pattern setups across categories:

| Category | Description |
|----------|-------------|
| **Confirmed** | Pattern complete, ready for entry |
| **Developing** | Pattern forming, watch for confirmation |
| **Emerging** | Initial pattern signs |
| **Watch Closely** | Potential setup developing |
| **Watch Only** | Early stage monitoring |

#### 7. VSR Score Tracker
Displays top VSR (Volume Spread Ratio) momentum tickers:

- Ticker symbol
- VSR Score (0-100)
- Current price
- Momentum %
- Sector classification
- Build status (Accumulating/Distributing)

#### 8. Reversal Pattern Counts
Shows Long vs Short reversal signals:

- **Long Count**: Number of bullish reversal patterns
- **Short Count**: Number of bearish reversal patterns
- **Ratio**: Long/Short ratio for bias determination

#### 9. PCR (Put-Call Ratio) Analysis
Options market sentiment indicator:

| Metric | Description |
|--------|-------------|
| **PCR OI** | Put-Call ratio based on Open Interest |
| **PCR Volume** | Put-Call ratio based on Volume |
| **PCR Combined** | Weighted combination |
| **Signal** | Bullish/Bearish/Neutral interpretation |

### Configuration Options (config.ini)

```ini
[Dashboard]
show_ml_insights = True
show_market_regime = True
show_sma_breadth = True
show_volume_breadth = True
show_reversal_patterns = True
show_g_pattern = True
show_vsr_tracker = True
show_optimal_conditions = True
show_momentum_scanner = False
show_regime_history = False
show_confidence_trend = False
show_weekly_bias = False
```

---

## Unified Market Momentum Dashboard (Port 8504)

### File Location
`/Users/maverick/PycharmProjects/Analysis/dashboard/unified_app.py`

### URL
http://localhost:8504

### Purpose
Comprehensive daily and hourly market breadth analysis with Fast/Slow weighted momentum tracking for India and US markets.

### Key Features

#### 1. Market Selection
- **India**: NSE stocks (FNO liquid universe)
- **US**: Major US equities

#### 2. View Modes
- **Daily**: End-of-day breadth analysis
- **Hourly**: Intraday breadth tracking

#### 3. Breadth Metrics

| Metric | Description |
|--------|-------------|
| **Binary Breadth %** | Simple % of stocks positive |
| **Weighted Breadth Index** | Volume-weighted breadth |
| **Market Momentum Index** | Composite momentum measure |

#### 4. Fast vs Slow WM (Weighted Momentum) Analysis

**Fast WM (EMA8-EMA13):**
- Short-term momentum indicator
- Quick to react to price changes
- Used for timing entries

**Slow WM (EMA21-EMA50):**
- Medium-term trend indicator
- Filters noise from fast WM
- Used for trend confirmation

**Pullback Analysis:**
- Tracks divergence between Fast and Slow WM
- Identifies pullback opportunities in trends
- Correction flags when Fast WM drops below Slow WM

#### 5. Breadth Chart Thresholds

```
Strong (65%): Bullish breadth threshold
Neutral (50%): Market equilibrium
Weak (40%): Bearish breadth threshold
```

#### 6. Top Movers Report
Displays selected tickers with:
- WM Score
- Volume Ratio
- Current Price
- Change %

**Selected India Tickers (FNO Liquid):**
- NIFTY, BANKNIFTY, FINNIFTY indices
- ~100 liquid FNO stocks (RELIANCE, HDFCBANK, INFY, TCS, etc.)

**Selected US Tickers:**
- Major tech: AAPL, GOOGL, META, MSFT, NVDA, AMZN
- Trading favorites: TSLA, AMD, COIN, MSTR
- ETFs: SPY, SOXX, GLD, SLV

#### 7. Year Trend Visualization
- 365-day breadth history
- 7-day and 21-day moving averages
- Regime distribution over time
- Fast vs Slow WM historical comparison

### Data Sources

| Data | Database | Table |
|------|----------|-------|
| Daily Breadth | `market_data.db` | `india_breadth`, `us_breadth` |
| Hourly Breadth | `hourly_data.db` | `india_hourly_breadth`, `us_hourly_breadth` |
| Daily Indicators | `market_data.db` | `india_indicators`, `us_indicators` |
| Hourly Indicators | `hourly_data.db` | `india_hourly_indicators`, `us_hourly_indicators` |

---

## How to Start the Dashboards

### Market Regime Dashboard (Port 8080)

```bash
# Option 1: Direct Python
python /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py

# Option 2: Background process
nohup python /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/dashboard_enhanced.py > /dev/null 2>&1 &

# Option 3: Via scheduled job (already configured)
# com.india-ts.market_regime_dashboard runs automatically
```

### Unified Momentum Dashboard (Port 8504)

```bash
# Option 1: Streamlit run
streamlit run /Users/maverick/PycharmProjects/Analysis/dashboard/unified_app.py --server.port 8504 --server.headless true

# Option 2: Background process
nohup streamlit run /Users/maverick/PycharmProjects/Analysis/dashboard/unified_app.py --server.port 8504 --server.headless true > /dev/null 2>&1 &
```

### Verify Dashboards Running

```bash
# Check ports
lsof -i :8080 -i :8504

# Check processes
ps aux | grep -E "(dashboard_enhanced|unified_app)" | grep -v grep
```

### Stop Dashboards

```bash
# Stop Market Regime dashboard
lsof -ti:8080 | xargs kill -9

# Stop Unified Momentum dashboard
lsof -ti:8504 | xargs kill -9
```

---

## Key Metrics Explained

### Market Regime Classification Logic

```python
def classify_regime(market_score, trend_score, volatility_score, confidence):
    """
    Regime Classification Rules:

    1. Strong Uptrend: market_score > 0.5 AND confidence > 0.7
    2. Uptrend: market_score > 0.2 AND confidence > 0.5
    3. Choppy Bullish: market_score > 0 AND confidence < 0.5
    4. Choppy: -0.2 < market_score < 0.2
    5. Choppy Bearish: market_score < 0 AND confidence < 0.5
    6. Downtrend: market_score < -0.2 AND confidence > 0.5
    7. Strong Downtrend: market_score < -0.5 AND confidence > 0.7
    """
```

### Breadth Calculation

```python
# Binary Breadth
binary_breadth_pct = (stocks_positive / total_stocks) * 100

# Weighted Breadth (volume-weighted)
weighted_breadth = sum(stock_return * stock_volume) / sum(stock_volume)

# Market Momentum Index
momentum_index = (weighted_breadth + binary_breadth) / 2
```

### Fast/Slow WM Calculation

```python
# Fast WM: Stocks above EMA8 and EMA13
fast_wm_positive = count(close > EMA8 AND close > EMA13)
fast_wm_pct = fast_wm_positive / total_stocks * 100

# Slow WM: Stocks above EMA21 and EMA50
slow_wm_positive = count(close > EMA21 AND close > EMA50)
slow_wm_pct = slow_wm_positive / total_stocks * 100

# Pullback Detection
pullback_depth = fast_wm_pct - slow_wm_pct
correction_flag = 1 if pullback_depth < -10 else 0
```

---

## Data Sources

### Market Regime Dashboard Data Files

| File | Location | Purpose |
|------|----------|---------|
| `latest_regime_summary.json` | `Market_Regime/regime_analysis/` | Current regime data |
| `market_breadth_latest.json` | `Market_Regime/breadth_data/` | Current breadth metrics |
| `sma_breadth_historical_latest.json` | `Market_Regime/historical_breadth_data/` | 7-month SMA history |
| `G_Pattern_Summary.txt` | `G_Pattern_Master/` | G Pattern categories |
| `vsr_tracker_{date}.log` | `logs/vsr_tracker/` | VSR scores log |
| `pcr_data.json` | `Market_Regime/data/` | Put-Call ratio data |

### Unified Dashboard Databases

| Database | Location | Tables |
|----------|----------|--------|
| `market_data.db` | `Analysis/data/warehouse/` | Daily breadth, indicators, prices |
| `hourly_data.db` | `Analysis/data/warehouse/` | Hourly breadth, indicators, prices |

---

## API Endpoints

### Market Regime Dashboard APIs

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/current_analysis` | GET | Current regime, scores, recommendations |
| `/api/regime_distribution` | GET | Regime distribution for charts |
| `/api/confidence_trend` | GET | Confidence history |
| `/api/metric_history/<metric>` | GET | Historical metric values |
| `/api/g_pattern_data` | GET | G Pattern categories and counts |
| `/api/vsr_scores` | GET | Top VSR momentum tickers |
| `/api/sma_breadth_history` | GET | 7-month SMA breadth data |
| `/api/sma-breadth-historical` | GET | Historical SMA breadth |
| `/api/sma-breadth-hourly` | GET | Hourly SMA breadth |
| `/api/reversal_patterns` | GET | Long/Short reversal counts |
| `/api/momentum_data` | GET | Market breadth momentum |
| `/api/momentum_trend` | GET | Momentum trend data |

### Sample API Response: `/api/current_analysis`

```json
{
  "timestamp": "2025-12-08T12:30:00",
  "regime": "uptrend",
  "confidence": 0.72,
  "strategy": "Favor long positions with tight stops",
  "ratio": 2.5,
  "counts": {"long": 25, "short": 10},
  "indicators": {
    "market_score": 0.35,
    "trend_score": 0.42,
    "volatility_score": 0.28,
    "breadth_score": 0.55
  },
  "position_recommendations": {
    "kelly_fraction": 0.12,
    "expected_value": 0.08,
    "win_probability": 0.62,
    "win_loss_ratio": 1.8,
    "max_positions": 3,
    "stop_loss_percent": 2.5,
    "preferred_direction": "LONG"
  },
  "pcr_analysis": {
    "pcr_oi": 0.95,
    "pcr_volume": 1.02,
    "pcr_combined": 0.98,
    "sentiment": "neutral"
  }
}
```

---

## Scheduled Jobs

| Job | Schedule | Dashboard |
|-----|----------|-----------|
| `com.india-ts.market_regime_analyzer_5min` | Every 5 min | Updates regime data |
| `com.india-ts.market_regime_dashboard` | 9:00 AM Mon-Fri | Starts dashboard |
| `com.india-ts.market_regime_shutdown` | 4:00 PM Mon-Fri | Stops dashboard |

---

## Troubleshooting

### Dashboard Not Loading

```bash
# Check if port is in use
lsof -i :8080
lsof -i :8504

# Kill existing process
lsof -ti:8080 | xargs kill -9

# Check logs
tail -f /Users/maverick/PycharmProjects/India-TS/Daily/logs/market_regime_dashboard.log
```

### No Data Displayed

1. Verify data files exist:
```bash
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/latest_regime_summary.json
```

2. Check regime analyzer is running:
```bash
launchctl list | grep market_regime
```

3. Manually run regime analyzer:
```bash
python /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/market_regime_analyzer.py
```

### Stale Data

```bash
# Check file modification time
ls -la /Users/maverick/PycharmProjects/India-TS/Daily/Market_Regime/regime_analysis/

# Force refresh by restarting analyzer
launchctl start com.india-ts.market_regime_analyzer_5min
```

---

## Summary

| Dashboard | Best For | Key Insight |
|-----------|----------|-------------|
| **Market Regime (8080)** | Trading decisions | Current regime + Kelly position sizing |
| **Unified Momentum (8504)** | Trend analysis | Fast/Slow WM divergence + pullback detection |

**Daily Workflow:**
1. Check Market Regime dashboard for current regime and position sizing
2. Use Unified Momentum for breadth trend confirmation
3. Monitor VSR scores for momentum opportunities
4. Track G Patterns for swing trade setups

---

*Document generated: 2025-12-08*
