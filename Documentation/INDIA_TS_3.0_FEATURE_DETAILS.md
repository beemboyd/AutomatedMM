# India TS 3.0 - Feature-by-Feature Documentation

## 1. Reversal Pattern Scanners

### Long Reversal Daily Scanner

**Purpose**: Identify high-probability bullish reversal patterns in daily timeframes.

**Location**: `Daily/scanners/Long_Reversal_Daily.py`

**Core Logic**:
```python
# 7-Point Scoring System
score = 0

# 1. Resistance Break (1 point)
if close > resistance_level and volume > avg_volume:
    score += 1

# 2. Confirmation Bars (1 point)
if green_bars >= 2 and all_closes_above_resistance:
    score += 1

# 3. Volume Expansion (1 point)
if volume > 1.5 * avg_volume_20:
    score += 1

# 4. Trend Support (1 point)
if price > sma_20 and sma_20 > sma_50:
    score += 1

# 5. Momentum Positive (1 point)
if rsi > 50 and macd > signal:
    score += 1

# 6. Price Action Quality (1 point)
if body_size > 0.7 * bar_range and upper_wick < 0.2 * bar_range:
    score += 1

# 7. Risk/Reward Favorable (1 point)
if potential_reward / potential_risk > 2:
    score += 1
```

**Key Parameters**:
- Minimum Score: 5/7
- ATR Multiplier: 2.5x for stop loss
- Look-back Period: 20 days
- Volume Threshold: 150% of average

**Output Format**:
```excel
Ticker | Entry | Stop Loss | Target | Score | R:R | Volume% | Sector
RELIANCE | 2850 | 2780 | 2950 | 6 | 1.43 | 180% | Oil & Gas
```

### Short Reversal Daily Scanner

**Purpose**: Identify high-probability bearish reversal patterns.

**Differences from Long Scanner**:
- Looks for support breaks instead of resistance breaks
- Requires red confirmation bars
- RSI < 50 and MACD < signal for momentum
- Lower wick analysis instead of upper wick

## 2. Market Regime Analysis System

### Market Regime Analyzer

**Purpose**: Classify overall market conditions and adjust trading parameters dynamically.

**Location**: `Daily/Market_Regime/market_regime_analyzer.py`

**Regime Classification Logic**:
```python
def determine_regime(long_count, short_count):
    if long_count == 0 and short_count == 0:
        return "choppy"
    
    ratio = long_count / short_count if short_count > 0 else float('inf')
    
    if ratio > 3:
        return "strong_uptrend"
    elif ratio > 2:
        return "uptrend"
    elif ratio > 1.2:
        return "choppy_bullish"
    elif ratio > 0.8:
        return "choppy"
    elif ratio > 0.5:
        return "choppy_bearish"
    elif ratio > 0.33:
        return "downtrend"
    else:
        return "strong_downtrend"
```

**Parameter Adjustments by Regime**:

| Regime | Position Size Multiplier | Stop Loss Multiplier | Max Positions |
|--------|-------------------------|---------------------|---------------|
| Strong Uptrend | 1.5x | 0.8x | 15 |
| Uptrend | 1.2x | 0.9x | 12 |
| Choppy Bullish | 1.0x | 1.0x | 10 |
| Choppy | 0.8x | 1.0x | 8 |
| Choppy Bearish | 0.7x | 1.1x | 7 |
| Downtrend | 0.5x | 1.2x | 5 |
| Strong Downtrend | 0.3x | 1.5x | 3 |

### Market Regime Predictor

**Purpose**: Use machine learning to predict next 30-minute market regime.

**Algorithm**: Random Forest Classifier

**Features Used**:
- Current and historical signal counts
- Breadth indicators
- Momentum scores
- Volatility metrics
- Time of day patterns

**Model Training Process**:
1. Collect features every 30 minutes
2. Make prediction for next period
3. Wait 30 minutes
4. Verify actual regime
5. Update model with outcome
6. Retrain periodically

## 3. Order Management System

### Place Orders Daily

**Purpose**: Execute trades based on scanner signals with proper risk management.

**Location**: `Daily/trading/place_orders_daily.py`

**Order Placement Logic**:
```python
def should_place_order(ticker, user):
    # Check 1: Not already in position
    if ticker in user_positions[user]:
        return False
    
    # Check 2: Under position limit
    if len(user_positions[user]) >= max_positions:
        return False
    
    # Check 3: Sufficient capital
    position_size = calculate_position_size(user, ticker)
    if position_size > available_capital[user]:
        return False
    
    # Check 4: Risk limits
    portfolio_heat = calculate_portfolio_heat(user)
    if portfolio_heat > max_portfolio_heat:
        return False
    
    # Check 5: Ticker cooldown
    if ticker in recent_trades[user]:
        if time_since_last_trade < cooldown_hours:
            return False
    
    return True
```

**Position Sizing Formula**:
```python
position_size = (account_capital * risk_per_trade) / (entry_price - stop_loss)
position_size *= regime_position_multiplier
position_size = min(position_size, max_position_size)
```

### Multi-User Context Management

**Purpose**: Enable multiple traders to use the system simultaneously with complete isolation.

**Key Features**:
- Separate API credentials per user
- Isolated state management
- User-specific logging
- Independent position tracking

**State Structure**:
```json
{
  "Sai": {
    "positions": [...],
    "orders": [...],
    "capital": 1000000,
    "last_update": "2025-06-25T15:30:00"
  },
  "Ravi": {
    "positions": [...],
    "orders": [...],
    "capital": 500000,
    "last_update": "2025-06-25T15:30:00"
  }
}
```

## 4. Risk Management System

### Stop Loss Watchdog

**Purpose**: Monitor positions and adjust stop losses based on price movement and volatility.

**Location**: `Daily/portfolio/SL_watchdog.py`

**Stop Loss Calculation**:
```python
def calculate_stop_loss(position):
    # Get current ATR
    atr = calculate_atr(position.ticker, period=14)
    atr_percentage = (atr / position.current_price) * 100
    
    # Determine multiplier based on volatility
    if atr_percentage < 2:
        multiplier = 1.0  # Tight stop for low volatility
    elif atr_percentage < 4:
        multiplier = 1.5  # Medium stop
    else:
        multiplier = 2.0  # Wide stop for high volatility
    
    # Apply regime adjustment
    multiplier *= regime_stop_multiplier
    
    # Calculate stop distance
    stop_distance = atr * multiplier
    
    # For long positions
    new_stop = position.current_price - stop_distance
    
    # Trailing stop logic - only move up
    if new_stop > position.current_stop:
        return new_stop
    else:
        return position.current_stop
```

**GTT Order Management**:
- Creates Good Till Triggered orders
- Updates only when stop moves favorably
- Handles order rejections gracefully
- Logs all stop loss modifications

### Portfolio Heat Calculation

**Purpose**: Monitor overall portfolio risk exposure.

**Formula**:
```python
portfolio_heat = sum(position_risk) / total_portfolio_value

where:
position_risk = (entry_price - stop_loss) * quantity

if portfolio_heat > 0.05:  # 5% limit
    block_new_positions = True
    tighten_stops = True
```

## 5. Analysis and Reporting

### Action Plan Generator

**Purpose**: Analyze ticker frequency across multiple days to identify persistent opportunities.

**Location**: `Daily/analysis/Action_plan.py`

**Tiering Logic**:

| Window | Tier 1 | Tier 2 | Tier 3 |
|--------|--------|--------|--------|
| 1-day | 4+ appearances | 2-3 appearances | 1 appearance |
| 2-day | 6+ appearances | 3-5 appearances | 1-2 appearances |
| 3-day | 9+ appearances | 5-8 appearances | 1-4 appearances |

**ML Enhancement**:
- Analyzes historical performance of frequent tickers
- Weights recommendations by success rate
- Considers sector rotation patterns

### Consolidated Score

**Purpose**: Rank opportunities by combining multiple factors.

**Scoring Components**:
1. Scanner score (0-7 points) - 40% weight
2. Frequency score (appearances) - 20% weight
3. Volume score (relative volume) - 15% weight
4. Momentum score (technical indicators) - 15% weight
5. Sector strength - 10% weight

**Output Format**:
```excel
Rank | Ticker | Total Score | Scanner | Frequency | Volume | Momentum | Sector
1 | RELIANCE | 8.5 | 6 | 4 | 180% | 75 | Strong
2 | TCS | 8.2 | 5 | 5 | 150% | 70 | Strong
```

## 6. Portfolio Management

### Portfolio Pruning

**Purpose**: Systematically remove underperforming positions to free up capital.

**Location**: `Daily/portfolio/Prune_Portfolio.py`

**Pruning Criteria**:
```python
def should_prune_position(position):
    # Criteria 1: Below moving average
    if position.current_price < position.sma_20:
        if position.holding_days > 5:
            return True
    
    # Criteria 2: Loss exceeding threshold
    if position.unrealized_pnl_percent < -5:
        return True
    
    # Criteria 3: Time-based stop
    if position.holding_days > 20 and position.unrealized_pnl_percent < 0:
        return True
    
    # Criteria 4: Regime-based
    if current_regime in ["downtrend", "strong_downtrend"]:
        if position.unrealized_pnl_percent < 2:
            return True
    
    return False
```

### Synch Zerodha Local

**Purpose**: Synchronize broker positions with local state management.

**Sync Process**:
1. Fetch all positions from Zerodha
2. Compare with local state
3. Identify discrepancies
4. Update local state
5. Log all changes
6. Alert on major differences

## 7. Scheduled Jobs System

### LaunchAgent Configuration

**Purpose**: Automate all system components on macOS.

**Schedule Optimization**:
```
Time Pattern:
:00 - Scanners start
:10 - Market regime analysis
:20 - Position sync
:30 - Scanners start again
:35 - Outcome resolver
:40 - Market regime analysis
:50 - Position sync
```

**Key Schedules**:

| Job | Schedule | Duration | Purpose |
|-----|----------|----------|---------|
| Action Plan | 8:30 AM | 5 min | Daily recommendations |
| Scanners | Every 30 min | 3 min | Signal generation |
| Market Regime | :10, :40 | 2 min | Regime analysis |
| SL Watchdog | Continuous | N/A | Stop monitoring |
| Portfolio Prune | 3:00 PM | 5 min | Position cleanup |

## 8. Data Management

### State Management

**File**: `trading_state.json`

**Structure**:
```json
{
  "metadata": {
    "last_updated": "2025-06-25T15:30:00",
    "version": "3.0"
  },
  "users": {
    "Sai": {
      "positions": {
        "RELIANCE": {
          "entry_price": 2850,
          "quantity": 10,
          "entry_time": "2025-06-25T09:30:00",
          "stop_loss": 2780,
          "product_type": "CNC"
        }
      },
      "orders": {},
      "capital": {
        "available": 500000,
        "deployed": 500000
      }
    }
  },
  "system": {
    "current_regime": "choppy_bullish",
    "last_scan": "2025-06-25T15:30:00"
  }
}
```

### Database Schema

**SQLite Database**: `regime_learning.db`

**Key Tables**:
- `regime_predictions`: ML predictions and outcomes
- `predictions`: Historical regime data
- `regime_changes`: Transition tracking
- `model_performance`: Accuracy metrics

---

*Each feature in India TS 3.0 is designed to work independently while contributing to the overall system intelligence. The modular architecture allows for easy updates and maintenance.*