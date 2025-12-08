# India-TS Trading System Architecture

**Created:** 2025-12-08
**Author:** Claude
**Purpose:** Visual architecture diagrams explaining the complete trading system

---

## 1. High-Level System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           INDIA-TS TRADING SYSTEM                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   SCANNERS   │    │   SERVICES   │    │  DASHBOARDS  │    │   TRADING    │       │
│  │              │    │              │    │              │    │              │       │
│  │ • VSR Hourly │    │ • VSR Track  │    │ • Regime     │    │ • Order Exec │       │
│  │ • Long Rev   │───▶│ • Hourly Trk │───▶│ • VSR        │───▶│ • SL Watch   │       │
│  │ • Short Rev  │    │ • Alert Svc  │    │ • Momentum   │    │ • Position   │       │
│  │ • KC Limit   │    │ • Telegram   │    │ • SL Watch   │    │   Mgmt       │       │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                   │               │
│         └───────────────────┴───────────────────┴───────────────────┘               │
│                                      │                                               │
│                          ┌───────────▼───────────┐                                  │
│                          │      ZERODHA API      │                                  │
│                          │    (Kite Connect)     │                                  │
│                          └───────────────────────┘                                  │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow Architecture

```
                                    ┌─────────────────┐
                                    │   NSE MARKET    │
                                    │     DATA        │
                                    └────────┬────────┘
                                             │
                                             ▼
                              ┌──────────────────────────┐
                              │     ZERODHA KITE API     │
                              │  • Historical Data       │
                              │  • Real-time Quotes      │
                              │  • Order Execution       │
                              └──────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │    SCANNERS      │    │    SERVICES      │    │    TRADING       │
         │                  │    │                  │    │                  │
         │ VSR_Momentum     │    │ vsr_tracker      │    │ place_orders     │
         │ Long_Reversal    │    │ hourly_tracker   │    │ SL_watchdog      │
         │ Short_Reversal   │    │ alert_tracker    │    │ position_mgmt    │
         │ KC_Upper/Lower   │    │ telegram_svc     │    │                  │
         └────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
                  │                       │                       │
                  ▼                       ▼                       ▼
         ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
         │   EXCEL/JSON     │    │   JSON/SQLite    │    │  ZERODHA API     │
         │   RESULTS        │    │   PERSISTENCE    │    │  ORDERS          │
         │                  │    │                  │    │                  │
         │ results/*.xlsx   │    │ vsr_ticker_      │    │ BUY/SELL         │
         │ results-s/*.xlsx │    │ persistence.json │    │ CNC/MIS          │
         │ scanners/Hourly/ │    │ audit_vsr.db     │    │ LIMIT/MARKET     │
         └────────┬─────────┘    └────────┬─────────┘    └──────────────────┘
                  │                       │
                  └───────────┬───────────┘
                              ▼
                   ┌──────────────────────┐
                   │     DASHBOARDS       │
                   │                      │
                   │ :8080  Market Regime │
                   │ :8504  Momentum      │
                   │ :3001  VSR Tracker   │
                   │ :2001  SL Watchdog   │
                   │ :5000  Health        │
                   └──────────────────────┘
```

---

## 3. Scanner Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SCANNER PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  INPUT                    PROCESSING                      OUTPUT            │
│  ─────                    ──────────                      ──────            │
│                                                                              │
│  ┌─────────────┐         ┌─────────────────┐         ┌─────────────────┐   │
│  │ Ticker.xlsx │         │ Technical       │         │ Excel Results   │   │
│  │ (1000+      │────────▶│ Analysis        │────────▶│                 │   │
│  │  stocks)    │         │                 │         │ Long_Reversal_  │   │
│  └─────────────┘         │ • Price Action  │         │ Daily_YYYYMMDD  │   │
│                          │ • Volume        │         │ .xlsx           │   │
│  ┌─────────────┐         │ • ATR           │         │                 │   │
│  │ Zerodha API │────────▶│ • EMA/SMA       │         │ Short_Reversal_ │   │
│  │ Historical  │         │ • Keltner       │         │ Daily_YYYYMMDD  │   │
│  │ Data        │         │ • RSI/MACD      │         │ .xlsx           │   │
│  └─────────────┘         │ • VSR Score     │         │                 │   │
│                          └─────────────────┘         │ VSR_YYYYMMDD_   │   │
│                                   │                  │ HHMMSS.xlsx     │   │
│                                   │                  └─────────────────┘   │
│                                   ▼                                        │
│                          ┌─────────────────┐         ┌─────────────────┐   │
│                          │ Pattern         │         │ HTML Reports    │   │
│                          │ Detection       │────────▶│                 │   │
│                          │                 │         │ Detailed_       │   │
│                          │ • Al Brooks     │         │ Analysis/       │   │
│                          │ • Reversal      │         │ Hourly/         │   │
│                          │ • Breakout      │         │ VSR_*.html      │   │
│                          │ • G-Pattern     │         └─────────────────┘   │
│                          └─────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

SCHEDULE:
─────────
• Long_Reversal_Daily    : Every 30 min (9:00 AM - 3:30 PM)
• Short_Reversal_Daily   : Every 30 min (9:00 AM - 3:30 PM)
• VSR_Momentum_Scanner   : Hourly (9:30 AM - 3:30 PM)
• KC_Upper/Lower_Limit   : Every 30 min (9:00 AM - 3:30 PM)
```

---

## 4. Order Execution & Position Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORDER EXECUTION & POSITION MANAGEMENT                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      VSR TICKER SELECTION                            │   │
│   │                                                                      │   │
│   │  vsr_ticker_persistence.json                                         │   │
│   │         │                                                            │   │
│   │         ▼                                                            │   │
│   │  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐         │   │
│   │  │ Score >= 60  │     │ Momentum     │     │ Positive     │         │   │
│   │  │              │ AND │ >= 2.0%      │ AND │ Momentum     │         │   │
│   │  └──────────────┘     └──────────────┘     └──────────────┘         │   │
│   │                              │                                       │   │
│   │                              ▼                                       │   │
│   │                   QUALIFIED VSR TICKERS                              │   │
│   └─────────────────────────────┬───────────────────────────────────────┘   │
│                                 │                                            │
│                                 ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      BREAKOUT DETECTION                              │   │
│   │                                                                      │   │
│   │  ┌────────────────────────────────────────────────────────┐         │   │
│   │  │  Get 4-Candle Hourly High (Breakout Level)             │         │   │
│   │  │                                                         │         │   │
│   │  │  Hour -4  │  Hour -3  │  Hour -2  │  Hour -1  │ Current │         │   │
│   │  │  ┌─┐      │  ┌─┐      │  ┌─┐      │  ┌─┐      │         │         │   │
│   │  │  │ │      │  │ │      │  │█│ ◄────│──│ │──────│─ HIGH   │         │   │
│   │  │  │ │      │  │█│      │  │ │      │  │█│      │         │         │   │
│   │  │  │█│      │  │ │      │  │ │      │  │ │      │         │         │   │
│   │  │  └─┘      │  └─┘      │  └─┘      │  └─┘      │         │         │   │
│   │  └────────────────────────────────────────────────────────┘         │   │
│   │                              │                                       │   │
│   │                              ▼                                       │   │
│   │         ┌─────────────────────────────────────────┐                 │   │
│   │         │  Current Price > Breakout Level?        │                 │   │
│   │         └─────────────────────────────────────────┘                 │   │
│   │                    │                    │                            │   │
│   │                   YES                   NO                           │   │
│   │                    │                    │                            │   │
│   │                    ▼                    ▼                            │   │
│   │         ┌──────────────────┐  ┌──────────────────┐                  │   │
│   │         │ Place LIMIT      │  │ SKIP             │                  │   │
│   │         │ Order at         │  │ (Not a breakout  │                  │   │
│   │         │ Breakout + 0.5%  │  │  yet)            │                  │   │
│   │         └──────────────────┘  └──────────────────┘                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                 │                                            │
│                                 ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                      POSITION SIZING                                 │   │
│   │                                                                      │   │
│   │  capital_deployment_percent = 1.0%                                   │   │
│   │                                                                      │   │
│   │  Available Capital: ₹10,00,000                                       │   │
│   │          │                                                           │   │
│   │          ▼                                                           │   │
│   │  Usable Capital = ₹10,00,000 × 1.0% = ₹10,000                        │   │
│   │          │                                                           │   │
│   │          ▼                                                           │   │
│   │  Per Position = ₹10,000 / 3 positions = ₹3,333                       │   │
│   │          │                                                           │   │
│   │          ▼                                                           │   │
│   │  Quantity = ₹3,333 / Stock Price                                     │   │
│   │                                                                      │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. SL Watchdog Architecture (ATR-based)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SL WATCHDOG (ATR-BASED) ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         STARTUP                                        │  │
│  │                                                                        │  │
│  │  1. Load positions from Zerodha (CNC/MIS/BOTH)                         │  │
│  │  2. Calculate 20-day ATR for each position                             │  │
│  │  3. Set initial stop loss based on volatility                          │  │
│  │  4. Start price polling thread (every 45 seconds)                      │  │
│  │  5. Start order processing thread                                      │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                        │
│                                     ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    ATR STOP LOSS CALCULATION                           │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  ATR% = (20-day ATR / Current Price) × 100                      │  │  │
│  │  │                                                                  │  │  │
│  │  │  Volatility Categories:                                          │  │  │
│  │  │  ┌──────────────┬──────────────┬──────────────┐                 │  │  │
│  │  │  │   LOW        │   MEDIUM     │   HIGH       │                 │  │  │
│  │  │  │  ATR < 2%    │  2% - 4%     │  ATR > 4%    │                 │  │  │
│  │  │  │              │              │              │                 │  │  │
│  │  │  │ Multiplier:  │ Multiplier:  │ Multiplier:  │                 │  │  │
│  │  │  │    1.0       │    1.5       │    2.0       │                 │  │  │
│  │  │  └──────────────┴──────────────┴──────────────┘                 │  │  │
│  │  │                                                                  │  │  │
│  │  │  Stop Loss = Current Price - (ATR × Multiplier)                  │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                        │
│                                     ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    TRAILING STOP LOGIC                                 │  │
│  │                                                                        │  │
│  │     Entry ────────────────────────────────────────────────────────▶   │  │
│  │       │                                                                │  │
│  │       │   Price rises to new high                                      │  │
│  │       │        │                                                       │  │
│  │       ▼        ▼                                                       │  │
│  │    ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐                                 │  │
│  │    │     │  │ NEW │  │     │  │     │   Position High                 │  │
│  │    │     │  │HIGH │  │     │  │     │   ──────────────                │  │
│  │    │     │  │  ▲  │  │     │  │     │                                 │  │
│  │    │     │  │  │  │  │     │  │     │                                 │  │
│  │    │     │  │  │  │  │     │  │     │                                 │  │
│  │    └──┬──┘  └──┼──┘  └──┬──┘  └──┬──┘                                 │  │
│  │       │       │        │        │                                      │  │
│  │    ───┼───────┼────────┼────────┼─────  Old Stop Loss                 │  │
│  │       │       │        │        │                                      │  │
│  │       │       │        │        │                                      │  │
│  │       │       ▼        │        │                                      │  │
│  │    ───┼───────────────┼────────┼─────  NEW Stop Loss (trails UP)      │  │
│  │       │               │        │                                       │  │
│  │                                                                        │  │
│  │  RULE: Stop loss only moves UP, never down                             │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                     │                                        │
│                                     ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    EXIT TRANCHES                                       │  │
│  │                                                                        │  │
│  │  LOW VOLATILITY (ATR < 2%):                                            │  │
│  │  ├── 50% at Stop Loss                                                  │  │
│  │  ├── 30% at 2× ATR Profit                                              │  │
│  │  └── 20% at 3× ATR Profit                                              │  │
│  │                                                                        │  │
│  │  MEDIUM VOLATILITY (2% - 4%):                                          │  │
│  │  ├── 40% at Stop Loss                                                  │  │
│  │  ├── 30% at 2.5× ATR Profit                                            │  │
│  │  └── 30% at 4× ATR Profit                                              │  │
│  │                                                                        │  │
│  │  HIGH VOLATILITY (ATR > 4%):                                           │  │
│  │  ├── 30% at Stop Loss                                                  │  │
│  │  ├── 30% at 3× ATR Profit                                              │  │
│  │  └── 40% at 5× ATR Profit                                              │  │
│  │                                                                        │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Market Regime Dashboard Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MARKET REGIME DASHBOARD (Port 8080)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA SOURCES                                     DASHBOARD SECTIONS        │
│  ────────────                                     ──────────────────        │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ latest_regime_      │                         │ CURRENT REGIME      │   │
│  │ summary.json        │────────────────────────▶│                     │   │
│  │                     │                         │ • Regime Badge      │   │
│  │ • market_regime     │                         │ • Confidence        │   │
│  │ • trend_analysis    │                         │ • Long/Short Ratio  │   │
│  │ • reversal_counts   │                         │ • Strategy          │   │
│  │ • position_recs     │                         │ • Proximity Bar     │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ position_           │                         │ KELLY CRITERION     │   │
│  │ recommendations     │────────────────────────▶│                     │   │
│  │                     │                         │ • Kelly %           │   │
│  │ • kelly_fraction    │                         │ • Expected Value    │   │
│  │ • win_probability   │                         │ • Win Probability   │   │
│  │ • win_loss_ratio    │                         │ • Max Positions     │   │
│  │ • expected_value    │                         │ • Stop Loss %       │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ sma_breadth_        │                         │ SMA BREADTH         │   │
│  │ historical_latest   │────────────────────────▶│                     │   │
│  │ .json               │                         │ • SMA20 Chart       │   │
│  │                     │                         │ • SMA50 Chart       │   │
│  │ • 7 months history  │                         │ • 5-day Trend       │   │
│  │ • sma20_percent     │                         │ • 20-day Trend      │   │
│  │ • sma50_percent     │                         │ • Market Score      │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ G_Pattern_          │                         │ G PATTERN           │   │
│  │ Summary.txt         │────────────────────────▶│                     │   │
│  │                     │                         │ • Confirmed         │   │
│  │ • Confirmed         │                         │ • Developing        │   │
│  │ • Developing        │                         │ • Emerging          │   │
│  │ • Emerging          │                         │ • Watch Closely     │   │
│  │ • Watch lists       │                         │ • Watch Only        │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ vsr_tracker_        │                         │ VSR TRACKER         │   │
│  │ {date}.log          │────────────────────────▶│                     │   │
│  │                     │                         │ • Top 15 Scores     │   │
│  │ • ticker scores     │                         │ • Momentum %        │   │
│  │ • momentum %        │                         │ • Build Status      │   │
│  │ • sector            │                         │ • Sector            │   │
│  │ • build status      │                         │ • Price             │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
│  ┌─────────────────────┐                         ┌─────────────────────┐   │
│  │ pcr_data.json       │                         │ PCR ANALYSIS        │   │
│  │                     │────────────────────────▶│                     │   │
│  │ • pcr_oi            │                         │ • PCR OI            │   │
│  │ • pcr_volume        │                         │ • PCR Volume        │   │
│  │ • sentiment         │                         │ • PCR Combined      │   │
│  │                     │                         │ • Signal            │   │
│  └─────────────────────┘                         └─────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Daily Trading Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DAILY TRADING WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  TIME        ACTION                          COMPONENT                       │
│  ────        ──────                          ─────────                       │
│                                                                              │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │8:00 │───▶│ MANUAL: Login Zerodha, refresh access token               │   │
│  │ AM  │    │         Update config.ini with new token                  │   │
│  └─────┘    └──────────────────────────────────────────────────────────┘   │
│     │                                                                        │
│     ▼                                                                        │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │8:30 │───▶│ Run: ./refresh_token_services.sh                          │   │
│  │ AM  │    │ • Kills all services                                      │   │
│  └─────┘    │ • Clears caches                                           │   │
│     │       │ • Restarts with new token                                 │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │9:00 │───▶│ AUTO: Scanners start (via plist)                          │   │
│  │ AM  │    │ • Long_Reversal_Daily                                     │   │
│  └─────┘    │ • Short_Reversal_Daily                                    │   │
│     │       │ • Market regime analyzer (5 min)                          │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │9:15 │───▶│ AUTO: Market opens                                        │   │
│  │ AM  │    │ • SL Watchdog starts (com.india-ts.sl_watchdog_start)     │   │
│  └─────┘    │ • Position sync starts (every 15 min)                     │   │
│     │       │ • Telegram alerts enabled                                 │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │9:30 │───▶│ AUTO: VSR Scanner starts (hourly)                         │   │
│  │ AM  │    │ • Scans 1000+ stocks                                      │   │
│  └─────┘    │ • Generates VSR scores                                    │   │
│     │       │ • Updates vsr_ticker_persistence.json                     │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │9:15-│    │ CONTINUOUS: Market monitoring                             │   │
│  │3:30 │───▶│ • Dashboards update every 5-30 seconds                    │   │
│  │ PM  │    │ • SL Watchdog polls prices every 45 seconds               │   │
│  └─────┘    │ • Telegram alerts on high-score tickers                   │   │
│     │       │ • Order execution on breakout confirmations               │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │3:30 │───▶│ AUTO: Market closes                                       │   │
│  │ PM  │    │ • SL Watchdog stops (com.india-ts.sl_watchdog_stop)       │   │
│  └─────┘    │ • VSR services stop (com.india-ts.vsr-shutdown)           │   │
│     │       │ • MIS positions squared by Zerodha                        │   │
│     ▼       └──────────────────────────────────────────────────────────┘   │
│  ┌─────┐    ┌──────────────────────────────────────────────────────────┐   │
│  │4:00 │───▶│ AUTO: End of day analysis                                 │   │
│  │ PM  │    │ • Momentum scanner runs                                   │   │
│  └─────┘    │ • Market regime dashboard updates                         │   │
│             │ • Performance metrics calculated                          │   │
│             └──────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Dashboard Port Map

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DASHBOARD PORT MAP                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│     PORT      DASHBOARD                    PURPOSE                           │
│     ────      ─────────                    ───────                           │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 2001 │──▶│ SL Watchdog Dashboard    │ Stop loss monitoring logs    │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 3001 │──▶│ VSR Tracker Dashboard    │ VSR momentum tickers          │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 3002 │──▶│ Hourly Long Tracker      │ Hourly long momentum          │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 3003 │──▶│ Short Momentum Dashboard │ Short reversal tracking       │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 3004 │──▶│ Hourly Short Tracker     │ Hourly short momentum         │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 5000 │──▶│ Health Dashboard         │ System health & job status    │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 8080 │──▶│ Market Regime Dashboard  │ Regime analysis & Kelly       │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
│    ┌──────┐   ┌─────────────────────────────────────────────────────────┐   │
│    │ 8504 │──▶│ Unified Momentum         │ Fast/Slow WM breadth          │   │
│    └──────┘   └─────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

Quick Access:
─────────────
• Market Regime:      http://localhost:8080
• Unified Momentum:   http://localhost:8504
• VSR Tracker:        http://localhost:3001
• SL Watchdog:        http://localhost:2001
• Health:             http://localhost:5000
```

---

## 9. File System Structure

```
/Users/maverick/PycharmProjects/India-TS/Daily/
│
├── scanners/                    # Market scanners
│   ├── VSR_Momentum_Scanner.py
│   ├── Long_Reversal_Daily.py
│   ├── Short_Reversal_Daily.py
│   ├── KC_Upper_Limit_Trending.py
│   └── Hourly/                  # Hourly scan results
│
├── services/                    # Background services
│   ├── vsr_tracker_service_enhanced.py
│   ├── hourly_tracker_service.py
│   └── short_momentum_tracker_service.py
│
├── dashboards/                  # Web dashboards
│   ├── vsr_tracker_dashboard.py          # Port 3001
│   ├── hourly_tracker_dashboard.py       # Port 3002
│   ├── short_momentum_dashboard.py       # Port 3003
│   ├── sl_watchdog_dashboard.py          # Port 2001
│   └── templates/
│
├── trading/                     # Order execution
│   ├── place_orders_daily_long_vsr.py
│   └── place_orders_vsr_momentum.py
│
├── portfolio/                   # Position management
│   ├── SL_watchdog.py           # ATR-based (DEFAULT)
│   ├── SL_watchdog_PSAR.py      # PSAR-based (alternative)
│   └── start_all_sl_watchdogs.py
│
├── Market_Regime/               # Regime analysis
│   ├── dashboard_enhanced.py    # Port 8080
│   ├── regime_analysis/
│   │   └── latest_regime_summary.json
│   ├── breadth_data/
│   └── historical_breadth_data/
│
├── alerts/                      # Notification services
│   ├── vsr_telegram_service_enhanced.py
│   └── telegram_notifier.py
│
├── data/                        # Persistence files
│   ├── vsr_ticker_persistence.json
│   ├── trading_state.json
│   └── audit_vsr.db
│
├── results/                     # Long reversal results
├── results-s/                   # Short reversal results
├── results-h/                   # Hourly long results
├── results-s-h/                 # Hourly short results
│
├── scheduler/                   # LaunchAgent plists
│   └── plists/
│
├── logs/                        # Log files
│   ├── {user}/
│   ├── vsr_tracker/
│   └── market_regime/
│
├── config.ini                   # Main configuration
├── refresh_token_services.sh    # Token refresh script
└── pre_market_setup_robust.sh   # Daily startup script
```

---

## 10. Summary Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                        INDIA-TS TRADING SYSTEM                               │
│                        ═══════════════════════                               │
│                                                                              │
│  ┌────────────────┐     ┌────────────────┐     ┌────────────────┐           │
│  │                │     │                │     │                │           │
│  │   DISCOVER     │────▶│    ANALYZE     │────▶│    EXECUTE     │           │
│  │                │     │                │     │                │           │
│  │  • Scanners    │     │  • Dashboards  │     │  • Orders      │           │
│  │  • Alerts      │     │  • Regime      │     │  • SL Watch    │           │
│  │  • Telegram    │     │  • Kelly       │     │  • Position    │           │
│  │                │     │                │     │    Mgmt        │           │
│  └────────────────┘     └────────────────┘     └────────────────┘           │
│         │                      │                      │                      │
│         │                      │                      │                      │
│         └──────────────────────┴──────────────────────┘                      │
│                                │                                             │
│                                ▼                                             │
│                      ┌────────────────┐                                     │
│                      │                │                                     │
│                      │   ZERODHA      │                                     │
│                      │   KITE API     │                                     │
│                      │                │                                     │
│                      └────────────────┘                                     │
│                                                                              │
│  DAILY SCHEDULE:                                                             │
│  ───────────────                                                             │
│  8:00 AM  ──▶  Token Refresh                                                │
│  9:00 AM  ──▶  Scanners Start                                               │
│  9:15 AM  ──▶  SL Watchdog + Sync Start                                     │
│  9:30 AM  ──▶  VSR Scanner (Hourly)                                         │
│  3:30 PM  ──▶  All Services Stop                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Document generated: 2025-12-08*
