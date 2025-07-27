# Dashboard V2 Architecture - Microservices Pattern

## Design Principles

1. **Independent Services**: Each dashboard section is served by its own microservice
2. **Fault Isolation**: If one service fails, others continue working
3. **Independent Updates**: Each section refreshes at its own interval
4. **Loose Coupling**: Services communicate through well-defined APIs
5. **Graceful Degradation**: Missing data shows loading state, not errors

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Dashboard Frontend                     │
│  (HTML + JavaScript with independent section loaders)    │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
             ▼                          ▼
┌────────────────────────┐  ┌────────────────────────────┐
│   API Gateway          │  │   Static Asset Server      │
│   (nginx/Flask)        │  │   (CSS, JS, Images)        │
└────────────┬───────────┘  └────────────────────────────┘
             │
    ┌────────┴────────┬────────────┬─────────────┬───────────┐
    ▼                 ▼            ▼             ▼           ▼
┌─────────┐    ┌──────────┐  ┌──────────┐  ┌─────────┐  ┌──────────┐
│ Market  │    │ Position │  │ Multi-   │  │ Breadth │  │ Index    │
│ Regime  │    │ Sizing   │  │ Timeframe│  │ Analysis│  │ Analysis │
│ Service │    │ Service  │  │ Service  │  │ Service │  │ Service  │
└─────────┘    └──────────┘  └──────────┘  └─────────┘  └──────────┘
    │               │             │             │            │
    ▼               ▼             ▼             ▼            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Shared Data Layer                         │
│          (Cache, Database, File System)                      │
└─────────────────────────────────────────────────────────────┘
```

## Service Definitions

### 1. Market Regime Service (`regime_service.py`)
- **Port**: 8081
- **Endpoints**:
  - `/api/regime/current` - Current regime and confidence
  - `/api/regime/history` - Historical regime changes
  - `/api/regime/strategy` - Current trading strategy
- **Refresh**: Every 30 minutes
- **Dependencies**: Scanner results, Index data

### 2. Position Sizing Service (`position_service.py`)
- **Port**: 8082
- **Endpoints**:
  - `/api/position/kelly` - Kelly Criterion calculations
  - `/api/position/recommendations` - Position size recommendations
  - `/api/position/risk` - Risk metrics
- **Refresh**: On regime change
- **Dependencies**: Market regime, Volatility data

### 3. Multi-Timeframe Service (`timeframe_service.py`)
- **Port**: 8083
- **Endpoints**:
  - `/api/timeframe/all` - All timeframe analysis
  - `/api/timeframe/{period}` - Specific timeframe (daily/weekly/monthly)
  - `/api/timeframe/alignment` - Cross-timeframe alignment score
- **Refresh**: Every 5 minutes
- **Dependencies**: Historical scan data

### 4. Breadth Analysis Service (`breadth_service.py`)
- **Port**: 8084
- **Endpoints**:
  - `/api/breadth/current` - Current market breadth
  - `/api/breadth/sma` - SMA breadth analysis
  - `/api/breadth/history` - Historical breadth data
- **Refresh**: Every 15 minutes
- **Dependencies**: Ticker data, Price feeds

### 5. Index Analysis Service (`index_service.py`)
- **Port**: 8085
- **Endpoints**:
  - `/api/index/sma` - Index vs SMA analysis
  - `/api/index/momentum` - Index momentum metrics
  - `/api/index/divergence` - Index divergences
- **Refresh**: Every 5 minutes
- **Dependencies**: Index price data

## Frontend Architecture

### HTML Structure (`dashboard_v2.html`)
```html
<div id="dashboard">
  <section id="regime-section" data-service="regime" data-refresh="1800">
    <div class="loading">Loading Market Regime...</div>
  </section>
  
  <section id="position-section" data-service="position" data-refresh="0">
    <div class="loading">Loading Position Sizing...</div>
  </section>
  
  <section id="timeframe-section" data-service="timeframe" data-refresh="300">
    <div class="loading">Loading Multi-Timeframe...</div>
  </section>
  
  <section id="breadth-section" data-service="breadth" data-refresh="900">
    <div class="loading">Loading Breadth Analysis...</div>
  </section>
  
  <section id="index-section" data-service="index" data-refresh="300">
    <div class="loading">Loading Index Analysis...</div>
  </section>
</div>
```

### JavaScript Module Pattern (`dashboard_v2.js`)
```javascript
class DashboardSection {
  constructor(sectionId, serviceUrl, refreshInterval) {
    this.section = document.getElementById(sectionId);
    this.serviceUrl = serviceUrl;
    this.refreshInterval = refreshInterval;
    this.lastUpdate = null;
    this.retryCount = 0;
  }
  
  async update() {
    try {
      const response = await fetch(this.serviceUrl);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const data = await response.json();
      this.render(data);
      this.lastUpdate = new Date();
      this.retryCount = 0;
    } catch (error) {
      this.handleError(error);
    }
  }
  
  render(data) {
    // Section-specific rendering logic
  }
  
  handleError(error) {
    this.retryCount++;
    if (this.retryCount > 3) {
      this.section.innerHTML = '<div class="error">Service temporarily unavailable</div>';
    }
    // Exponential backoff retry
    setTimeout(() => this.update(), Math.min(60000, 1000 * Math.pow(2, this.retryCount)));
  }
  
  startAutoRefresh() {
    if (this.refreshInterval > 0) {
      setInterval(() => this.update(), this.refreshInterval * 1000);
    }
  }
}
```

## Implementation Benefits

1. **Resilience**: One service failure doesn't break the dashboard
2. **Performance**: Parallel loading of all sections
3. **Scalability**: Easy to add new sections/services
4. **Maintainability**: Clear separation of concerns
5. **Testing**: Each service can be tested independently
6. **Deployment**: Services can be updated independently

## Migration Plan

### Phase 1: Service Extraction
1. Create service modules for each dashboard section
2. Implement shared data access layer
3. Add service health checks

### Phase 2: API Gateway
1. Set up Flask API gateway on port 8080
2. Configure routing to microservices
3. Add request caching and rate limiting

### Phase 3: Frontend Refactor
1. Create modular JavaScript components
2. Implement progressive loading
3. Add error boundaries and fallbacks

### Phase 4: Monitoring
1. Add service health dashboard
2. Implement logging aggregation
3. Set up alerts for service failures

## Service Communication

### Inter-Service Communication
- Use Redis pub/sub for event notifications
- REST APIs for data queries
- Shared cache for common data

### Data Consistency
- Each service owns its data domain
- Event-driven updates for dependent data
- Eventual consistency model

## Deployment Strategy

### Development
```bash
# Start all services
./start_dashboard_services.sh

# Or start individually
python regime_service.py &
python position_service.py &
python timeframe_service.py &
python breadth_service.py &
python index_service.py &
```

### Production
- Use supervisord or systemd for process management
- nginx as reverse proxy and load balancer
- Redis for caching and pub/sub
- PostgreSQL for persistent storage

## Error Handling

1. **Service Level**: Return standardized error responses
2. **Gateway Level**: Circuit breakers and fallbacks
3. **Frontend Level**: Graceful degradation and retry logic
4. **User Level**: Clear error messages and recovery options