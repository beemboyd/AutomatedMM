# MCP Servers for Market Analysis

This directory contains MCP (Model Context Protocol) servers for analyzing market conditions and portfolio performance.

## Servers

### 1. Portfolio Performance Server (`portfolio_mcp_server.py`)
Analyzes transaction data, order history, and portfolio metrics.

**Features:**
- Transaction analysis from Excel files
- Order performance tracking by user
- Portfolio metrics calculation (PnL, win rate, Sharpe ratio)
- Top gainers/losers identification

### 2. Market Conditions Server (`market_mcp_server.py`)
Provides market regime analysis, breadth indicators, and trading insights.

**Features:**
- Current market regime and predictions
- Market breadth analysis
- Reversal pattern counts
- Index performance vs SMA
- AI-generated market insights

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Running the servers

```bash
# Portfolio server
python portfolio_mcp_server.py

# Market server
python market_mcp_server.py
```

### Example Queries

#### Portfolio Analysis

```python
# Get portfolio metrics for the last week
{
  "tool": "get_portfolio_metrics",
  "arguments": {
    "period": "week",
    "user": "Sai"  # Optional
  }
}

# Analyze transactions
{
  "tool": "analyze_transactions",
  "arguments": {
    "analysis_type": "top_gainers",
    "start_date": "2025-07-01",
    "end_date": "2025-07-19"
  }
}

# Get top transactions this week
{
  "tool": "get_top_transactions",
  "arguments": {
    "count": 10,
    "type": "gainers",
    "period": "week"
  }
}

# Analyze order performance
{
  "tool": "analyze_order_performance",
  "arguments": {
    "user": "Som",
    "days": 7
  }
}
```

#### Market Analysis

```python
# Get current market regime
{
  "tool": "get_market_regime",
  "arguments": {
    "include_history": true,
    "history_days": 7
  }
}

# Analyze market breadth
{
  "tool": "analyze_market_breadth",
  "arguments": {
    "period": "3days",
    "metrics": ["advance_decline_ratio", "bullish_percent"]
  }
}

# Get reversal analysis
{
  "tool": "get_reversal_analysis",
  "arguments": {
    "type": "both",
    "include_tickers": true
  }
}

# Get market insights
{
  "tool": "get_market_insights",
  "arguments": {
    "focus": "trading"
  }
}
```

## Resources

### Portfolio Resources
- `portfolio://transactions/{filename}` - Transaction Excel files
- `portfolio://orders/{user}` - User order history

### Market Resources
- `market://regime/latest` - Latest market regime analysis
- `market://regime/history` - Historical regime data
- `market://breadth/latest` - Latest breadth indicators
- `market://patterns/g-pattern` - G-Pattern analysis

## Data Sources

The servers analyze data from:
- `/Daily/data/Transactions/` - Transaction Excel files
- `/Daily/Current_Orders/` - Order history by user
- `/Daily/Market_Regime/` - Market regime and breadth data
- `/Daily/G_Pattern_Master/` - Pattern analysis
- `/Daily/Detailed_Analysis/` - Technical analysis reports