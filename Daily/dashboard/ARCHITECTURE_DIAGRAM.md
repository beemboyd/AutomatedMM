# Dashboard Architecture Diagrams

## Current Monolithic Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Browser                          │
└─────────────────────────┬───────────────────────────────┘
                          │ Single Request
                          ▼
┌─────────────────────────────────────────────────────────┐
│              dashboard_enhanced.py (Port 8080)          │
│  ┌─────────────────────────────────────────────────┐   │
│  │         Single Flask Application                 │   │
│  │  ┌──────────────┐  ┌──────────────┐            │   │
│  │  │Market Regime │  │Kelly Calc    │            │   │
│  │  │Analysis      │  │              │            │   │
│  │  └──────┬───────┘  └──────┬───────┘            │   │
│  │         │                  │                    │   │
│  │  ┌──────▼──────────────────▼──────┐            │   │
│  │  │    generate_regime_report()     │            │   │
│  │  │  (500+ lines, tightly coupled)  │            │   │
│  │  └──────┬──────────────────────────┘            │   │
│  │         │                                       │   │
│  │  ┌──────▼──────────────────────────┐            │   │
│  │  │   Single API Response (3MB+)     │            │   │
│  │  └──────────────────────────────────┘            │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                   [If any part fails,
                    entire dashboard fails]
```

## New Microservices Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Browser                          │
│  ┌────────┬────────┬────────┬────────┬────────┐       │
│  │Regime  │Kelly   │Time-   │Breadth │Index   │       │
│  │Widget  │Widget  │frame   │Widget  │Widget  │       │
│  └───┬────┴───┬────┴───┬────┴───┬────┴───┬────┘       │
└──────┼────────┼────────┼────────┼────────┼────────────┘
       │        │        │        │        │
       │   Parallel Requests (Async)       │
       ▼        ▼        ▼        ▼        ▼
┌─────────────────────────────────────────────────────────┐
│              API Gateway (Port 8080)                    │
│         (Routes, Caches, Circuit Breakers)              │
└──┬────────┬────────┬────────┬────────┬────────────────┘
   │        │        │        │        │
   ▼        ▼        ▼        ▼        ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Regime│ │Kelly │ │Time- │ │Breadth│ │Index │
│ :8081│ │ :8082│ │frame │ │ :8084│ │ :8085│
│      │ │      │ │ :8083│ │      │ │      │
│ 50KB │ │ 10KB │ │ 30KB │ │ 20KB │ │ 15KB │
└──────┘ └──────┘ └──────┘ └──────┘ └──────┘
   │        │        │        │        │
   └────────┴────────┼────────┴────────┘
                     ▼
              [If one fails, others
               continue working]
```

## Request Flow Comparison

### Current System - Sequential Processing
```
Time →
0ms    [Browser Request]
       |
100ms  ├─[Load Scan Results]
       |
300ms  ├─[Calculate Regime]
       |
500ms  ├─[Calculate Kelly]
       |
700ms  ├─[Multi-timeframe Analysis]
       |
900ms  ├─[Breadth Calculation]
       |
1100ms ├─[Index Analysis]
       |
1300ms ├─[Combine Everything]
       |
1500ms └─[Send Response] → Browser renders everything
```

### New System - Parallel Processing
```
Time →
0ms    [Browser Request]
       ├─[Regime Service]──────→ 200ms ─┐
       ├─[Kelly Service]───────→ 100ms ─┤
       ├─[Timeframe Service]───→ 300ms ─┼─→ Browser renders progressively
       ├─[Breadth Service]─────→ 250ms ─┤
       └─[Index Service]───────→ 150ms ─┘
```

## Failure Scenarios

### Current: Database Connection Lost
```
┌─────────────────┐
│   Dashboard     │
│      ❌         │  ← Entire dashboard shows error
│  "Error: DB     │
│  Connection     │
│   Failed"       │
└─────────────────┘
```

### New: Database Connection Lost
```
┌─────────────────────────────────┐
│          Dashboard              │
├─────────────┬─────────────┬─────┤
│  Regime     │   Kelly     │Index│
│    ⚠️       │     ⚠️      │  ✅ │
│ (cached)    │  (cached)   │(live)│
├─────────────┴─────────────┴─────┤
│         Breadth: ❌              │
│    "Temporarily unavailable"    │
│       (retrying in 5s...)       │
└─────────────────────────────────┘
```

## Service Communication Pattern

```
                 ┌─────────────┐
                 │ Event Bus   │
                 │  (Redis)    │
                 └──────┬──────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
    ▼                   ▼                   ▼
┌────────┐         ┌────────┐         ┌────────┐
│Scanner │         │ Regime │         │ Kelly  │
│Complete│ ──────► │ Update │ ──────► │ Update │
│ Event  │         │ Event  │         │ Event  │
└────────┘         └────────┘         └────────┘
```

## Caching Hierarchy

```
┌─────────────────────────────────────────┐
│          Browser Cache (5 min)          │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│      API Gateway Cache (2 min)          │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│     Service Memory Cache (5 min)        │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│        Redis Cache (30 min)             │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│      Data Source (Database/Files)       │
└─────────────────────────────────────────┘
```

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│            Load Balancer                │
└────────────────────┬────────────────────┘
                     ▼
┌─────────────────────────────────────────┐
│          Nginx (Reverse Proxy)          │
└──┬──────┬──────┬──────┬──────┬─────────┘
   │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│ S1  ││ S2  ││ S3  ││ S4  ││ S5  │
└─────┘└─────┘└─────┘└─────┘└─────┘
   │      │      │      │      │
   └──────┴──────┼──────┴──────┘
                 ▼
         ┌──────────────┐
         │  Shared      │
         │  Resources   │
         │  - Redis     │
         │  - Files     │
         │  - Database  │
         └──────────────┘
```