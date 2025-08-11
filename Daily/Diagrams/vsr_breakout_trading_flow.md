# VSR Breakout Trading System Flow

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     VSR BREAKOUT TRADING SYSTEM                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         USER AUTHENTICATION                          │
│  - Load config.ini                                                   │
│  - Select user account                                               │
│  - Initialize context manager                                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      VSR DASHBOARD INTEGRATION                       │
│  ┌──────────────────┐        ┌──────────────────────┐              │
│  │ VSR Dashboard    │ ──API──▶│ Fetch VSR Tickers   │              │
│  │ (Port 3001)      │        │ - Score >= 60        │              │
│  └──────────────────┘        │ - Momentum >= 2%     │              │
│                              └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SIGNAL GENERATION                             │
│  ┌──────────────────┐        ┌──────────────────────┐              │
│  │ Fetch Hourly     │        │ Calculate Breakout   │              │
│  │ Candlestick Data │ ──────▶│ - Previous High      │              │
│  └──────────────────┘        │ - Entry Level        │              │
│                              │ - Stop Loss (2%)     │              │
│                              └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       USER INTERACTION                               │
│  ┌──────────────────┐        ┌──────────────────────┐              │
│  │ Display          │        │ User Selection       │              │
│  │ Candidates       │ ──────▶│ - Exclude tickers    │              │
│  │ - Score          │        │ - Confirm orders     │              │
│  │ - Momentum       │        └──────────────────────┘              │
│  │ - Price          │                                               │
│  └──────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       ORDER EXECUTION                                │
│  ┌──────────────────┐        ┌──────────────────────┐              │
│  │ Position Sizing  │        │ Place Orders         │              │
│  │ - 1% of Portfolio│ ──────▶│ - LIMIT orders       │              │
│  │ - Max 5 positions│        │ - CNC product        │              │
│  └──────────────────┘        │ - Update state       │              │
│                              └──────────────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌──────────────┐      HTTP GET       ┌──────────────────┐
│ VSR Dashboard│ ──────────────────▶ │ place_orders_    │
│  Port 3001   │                     │ daily_long_vsr.py│
└──────────────┘                     └──────────────────┘
                                             │
                                             ▼
                                     ┌──────────────────┐
                                     │ Filter & Sort    │
                                     │ - Score >= 60    │
                                     │ - Momentum > 2%  │
                                     └──────────────────┘
                                             │
                                             ▼
┌──────────────┐      Kite API       ┌──────────────────┐
│   Zerodha    │ ◀────────────────── │ Fetch Hourly     │
│  Historical  │                     │ Candle Data      │
└──────────────┘                     └──────────────────┘
                                             │
                                             ▼
                                     ┌──────────────────┐
                                     │ Calculate Entry  │
                                     │ & Stop Loss      │
                                     └──────────────────┘
                                             │
                                             ▼
                                     ┌──────────────────┐
                                     │ User Approval    │
                                     └──────────────────┘
                                             │
                                             ▼
┌──────────────┐      Kite API       ┌──────────────────┐
│   Zerodha    │ ◀────────────────── │ Place Orders     │
│   Broker     │                     │ (LIMIT, CNC)     │
└──────────────┘                     └──────────────────┘
```

## Execution Timeline (Automated Mode - Future)

```
10:00 AM ─────┬───── Market Opens
              │
10:05 AM ─────┼───── First VSR Scan & Trade
              │       - Fetch VSR tickers
              │       - Check hourly breakouts
              │       - Place orders
              │
11:05 AM ─────┼───── Second VSR Scan & Trade
              │       - Update existing positions
              │       - Add new breakouts
              │
12:05 PM ─────┼───── Third VSR Scan & Trade
              │       - Monitor performance
              │       - Adjust stops if needed
              │
1:05 PM ──────┼───── Final VSR Scan & Trade
              │       - Last entry opportunity
              │       - Position review
              │
3:30 PM ──────┴───── Market Closes
```

## Risk Management Flow

```
┌──────────────────────────┐
│   Portfolio Value        │
│   ₹10,00,000            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Position Size = 1%      │
│  ₹10,000 per position    │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Max Positions = 5       │
│  Max Risk = 5% Portfolio │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│  Stop Loss = 2%          │
│  Risk per trade = ₹200   │
└──────────────────────────┘
```

## State Management

```
┌──────────────────────────────────────────────────────┐
│                   STATE MANAGER                       │
├──────────────────────────────────────────────────────┤
│  Position Tracking:                                   │
│  - Ticker symbol                                      │
│  - Entry price & quantity                             │
│  - Stop loss level                                    │
│  - VSR score at entry                                 │
│  - Momentum at entry                                  │
│  - Order ID                                           │
│  - Entry timestamp                                    │
└──────────────────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────┐
│                  POSITION WATCHDOG                    │
├──────────────────────────────────────────────────────┤
│  Monitoring:                                          │
│  - Real-time price tracking                           │
│  - Stop loss triggers                                 │
│  - Profit target monitoring                           │
│  - Time-based exits                                   │
└──────────────────────────────────────────────────────┘
```

## Error Handling

```
┌─────────────────┐
│ Error Detection │
└────────┬────────┘
         │
         ▼
    ┌────────────┐
    │ Error Type │
    └────┬───────┘
         │
    ┌────┴────────────────┬─────────────────┬──────────────┐
    ▼                      ▼                 ▼              ▼
┌──────────┐      ┌──────────────┐  ┌──────────────┐ ┌──────────┐
│ API Error│      │ Market Error │  │ Data Error   │ │ System   │
│          │      │              │  │              │ │ Error    │
└────┬─────┘      └──────┬───────┘  └──────┬───────┘ └────┬─────┘
     │                   │                  │              │
     ▼                   ▼                  ▼              ▼
┌──────────┐      ┌──────────────┐  ┌──────────────┐ ┌──────────┐
│ Retry    │      │ Skip Ticker  │  │ Use Fallback │ │ Alert &  │
│ Logic    │      │              │  │ Data         │ │ Exit     │
└──────────┘      └──────────────┘  └──────────────┘ └──────────┘
```

## Integration Points

```
              ┌────────────────────────────┐
              │   VSR Breakout Trading     │
              └────────────┬───────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ VSR Dashboard│  │Position      │  │ Daily Reports│
│ (Port 3001)  │  │Watchdog      │  │ Generator    │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Telegram     │  │ Stop Loss    │  │ P&L Tracker  │
│ Alerts       │  │ Monitor      │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

*Created: August 11, 2025*
*Version: 1.0*