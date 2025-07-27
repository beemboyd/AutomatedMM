# Dashboard Microservices Architecture Plan

## Executive Summary

The current monolithic dashboard has become fragile - each change risks breaking unrelated sections. This document outlines a microservices architecture that provides:
- **Fault isolation** - One section failing doesn't affect others
- **Independent updates** - Each section refreshes at its own pace
- **Better performance** - Parallel loading and caching
- **Easier maintenance** - Clear separation of concerns

## Current Problems

1. **Tight Coupling**: All sections depend on a single data structure
2. **Cascade Failures**: One error can break the entire dashboard
3. **Slow Updates**: Everything refreshes together, even if only one section needs updating
4. **Testing Difficulty**: Can't test sections independently
5. **Development Bottleneck**: Changes require understanding the entire system

## Proposed Architecture

### Overview
```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Port 8080)                     │
│                  Single Page Application                     │
│            (Modular JavaScript + Progressive Loading)        │
└───────────────────────┬─────────────────────────────────────┘
                        │ AJAX/Fetch
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (Port 8080)                   │
│                 (Routes, Auth, Rate Limiting)                │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐
│Regime│  │Kelly │  │Time- │  │Breadth│ │Index │
│Service│ │Service│ │frame │  │Service│ │Service│
│ :8081│  │ :8082│  │ :8083│  │ :8084│  │ :8085│
└──────┘  └──────┘  └──────┘  └──────┘  └──────┘
   │          │          │          │          │
   └──────────┴──────────┼──────────┴──────────┘
                         ▼
              ┌─────────────────────┐
              │   Shared Services   │
              │  - Redis Cache      │
              │  - File System      │
              │  - Event Bus        │
              └─────────────────────┘
```

### Service Breakdown

#### 1. **Market Regime Service** (Port 8081)
- **Purpose**: Market regime determination and confidence
- **Endpoints**:
  ```
  GET /api/regime/current     → Current regime & confidence
  GET /api/regime/history     → Last 7 days of regime changes
  GET /api/regime/prediction  → ML-based regime prediction
  ```
- **Refresh**: Every 30 minutes (or on scan completion)
- **Dependencies**: Scanner results, ML model

#### 2. **Kelly Position Service** (Port 8082)
- **Purpose**: Position sizing calculations
- **Endpoints**:
  ```
  GET /api/position/kelly     → Kelly criterion calculations
  GET /api/position/risk      → Risk metrics & limits
  GET /api/position/guidance  → Specific recommendations
  ```
- **Refresh**: On regime change
- **Dependencies**: Market regime, volatility data

#### 3. **Multi-Timeframe Service** (Port 8083)
- **Purpose**: Cross-timeframe market analysis
- **Endpoints**:
  ```
  GET /api/timeframe/all      → All timeframes summary
  GET /api/timeframe/daily    → Daily analysis
  GET /api/timeframe/weekly   → Weekly analysis
  GET /api/timeframe/monthly  → Monthly analysis
  ```
- **Refresh**: Every 5 minutes
- **Dependencies**: Historical scan data

#### 4. **Market Breadth Service** (Port 8084)
- **Purpose**: Market internals and breadth metrics
- **Endpoints**:
  ```
  GET /api/breadth/current    → Current A/D, breadth
  GET /api/breadth/sma        → SMA breadth analysis
  GET /api/breadth/volume     → Volume breadth metrics
  ```
- **Refresh**: Every 15 minutes
- **Dependencies**: Ticker data, price feeds

#### 5. **Index Analysis Service** (Port 8085)
- **Purpose**: Major index technical analysis
- **Endpoints**:
  ```
  GET /api/index/sma          → Index vs SMA positions
  GET /api/index/momentum     → Momentum indicators
  GET /api/index/divergence   → Price/breadth divergences
  ```
- **Refresh**: Every 5 minutes
- **Dependencies**: Index price data

### Frontend Architecture

#### Component Structure
```javascript
// Each section is an independent component
class DashboardSection {
  constructor(config) {
    this.id = config.id;
    this.service = config.service;
    this.refreshInterval = config.refreshInterval;
    this.retryPolicy = config.retryPolicy;
  }
  
  async load() {
    try {
      const data = await this.fetchData();
      this.render(data);
      this.scheduleNextUpdate();
    } catch (error) {
      this.handleError(error);
    }
  }
  
  handleError(error) {
    // Show graceful error state
    // Implement exponential backoff
    // Don't crash other sections
  }
}
```

#### Progressive Loading
1. Load critical sections first (regime, position sizing)
2. Load supporting sections async (breadth, timeframes)
3. Show skeleton loaders during fetch
4. Cache successful responses

### Data Flow

#### Event-Driven Updates
```
Scanner Completion → Event Bus → Regime Service → Position Service
                        ↓
                  Breadth Service
                        ↓
                  Index Service
```

#### Caching Strategy
- **L1 Cache**: In-memory in each service (5 min TTL)
- **L2 Cache**: Redis shared cache (30 min TTL)
- **L3 Cache**: File system for historical data

### Implementation Plan

#### Phase 1: Service Extraction (Week 1)
1. Create base service framework
2. Extract regime calculation into service
3. Extract Kelly calculations into service
4. Test services independently

#### Phase 2: Additional Services (Week 2)
1. Create multi-timeframe service
2. Create breadth analysis service
3. Create index analysis service
4. Implement shared cache layer

#### Phase 3: Frontend Refactor (Week 3)
1. Create modular JavaScript components
2. Implement progressive loading
3. Add error boundaries
4. Create unified API client

#### Phase 4: Integration (Week 4)
1. Setup API gateway
2. Implement service discovery
3. Add monitoring/alerting
4. Performance optimization

### Benefits Over Current System

1. **Resilience**
   - Current: One error breaks everything
   - New: Services fail independently

2. **Performance**
   - Current: 3-5 second full page load
   - New: <1 second initial render, progressive updates

3. **Development**
   - Current: Must understand entire system
   - New: Work on services independently

4. **Testing**
   - Current: Complex integration tests only
   - New: Simple unit tests per service

5. **Deployment**
   - Current: Deploy everything together
   - New: Deploy services independently

### Technical Stack

- **Services**: Python/Flask (lightweight, familiar)
- **Cache**: Redis (fast, supports pub/sub)
- **Frontend**: Vanilla JavaScript modules (no framework overhead)
- **API Gateway**: Flask with route aggregation
- **Process Manager**: Supervisord (simple, reliable)

### Migration Strategy

1. **Parallel Run**: New system runs alongside old
2. **Gradual Cutover**: Redirect sections one at a time
3. **Rollback Ready**: Can switch back instantly
4. **A/B Testing**: Compare performance/reliability

### Monitoring & Observability

Each service exposes:
- `/health` - Service health check
- `/metrics` - Performance metrics
- `/debug` - Debug information

Centralized logging aggregates all service logs for easy debugging.

### Example Service Implementation

```python
from base_service import BaseService

class RegimeService(BaseService):
    def __init__(self):
        super().__init__('regime-service', port=8081, cache_ttl=1800)
        self.setup_routes()
    
    def setup_routes(self):
        @self.add_route('/api/regime/current')
        @self.cache_result(ttl=300)
        def get_current_regime():
            # Load scan results
            # Calculate regime
            # Return standardized response
            return self.standardize_response({
                'regime': 'strong_downtrend',
                'confidence': 0.85,
                'ratio': 0.24
            })
```

### Risk Mitigation

1. **Service Discovery**: Hard-coded initially, add consul later
2. **Circuit Breakers**: Prevent cascade failures
3. **Rate Limiting**: Prevent service overload
4. **Graceful Degradation**: Show cached/default data
5. **Health Monitoring**: Auto-restart failed services

### Success Metrics

- **Availability**: 99.9% uptime per service
- **Performance**: <100ms service response time
- **Error Rate**: <0.1% failed requests
- **Development**: 50% faster feature delivery
- **Testing**: 80% code coverage per service

## Conclusion

This microservices architecture solves our current problems while providing a foundation for future growth. The modular design allows us to:
- Add new features without breaking existing ones
- Scale services independently based on load
- Maintain and debug more effectively
- Deliver a better user experience

The implementation is pragmatic, using proven technologies and patterns that the team already knows. The migration can be done gradually with minimal risk.