# Zerodha API Integration for Portfolio Analysis

## Overview
The portfolio analysis script has been enhanced to fetch live positions directly from your Zerodha account using the Zerodha API. This provides real-time portfolio analysis based on actual positions.

## Usage

### Basic Command (Local State File)
```bash
python3 ML-Framework/scripts/analyze_my_portfolio.py
```

### With Zerodha API Integration
```bash
python3 ML-Framework/scripts/analyze_my_portfolio.py --use-zerodha
```

### Skip HTML Report Generation
```bash
python3 ML-Framework/scripts/analyze_my_portfolio.py --no-html
```

## Features

### 1. Zerodha Position Fetching
- Automatically queries your Zerodha account for open positions
- Fetches position details including:
  - Trading symbol
  - Quantity
  - Average price
  - Product type (CNC/MIS)
  - Exchange

### 2. HTML Report Generation
The script now generates comprehensive HTML reports with:

- **Portfolio Summary**: Total positions, value, and P&L
- **Regime Distribution Chart**: Visual breakdown of market regimes (requires plotly)
- **Urgent Actions Alert**: Highlights positions requiring immediate attention
- **Detailed Position Table**: Complete analysis of each position including:
  - Entry/Current prices
  - P&L in absolute and percentage terms
  - Market regime classification
  - Recommended actions
  - Stop loss levels
  - Position sizing recommendations

### 3. Action Recommendations
Positions are categorized into action groups:
- **REDUCE_OR_EXIT**: Exit or significantly reduce positions immediately
- **CONSIDER_EXIT**: Consider exiting these positions
- **REDUCE_SIZE**: Reduce position size due to high volatility
- **MONITOR**: Continue monitoring, maintain current position
- **HOLD_OR_ADD**: Favorable regime, can hold or add to position

### 4. Risk Management Checklist
The report includes a comprehensive risk management checklist:
- Stop loss updates for each position
- Position sizing recommendations
- Urgent actions summary
- Market regime insights

## Report Output

Reports are saved in multiple formats:
```
ML-Framework/results/portfolio_analysis/
├── portfolio_regime_YYYYMMDD_HHMMSS.csv   # Spreadsheet format
├── portfolio_regime_YYYYMMDD_HHMMSS.json  # Raw data
└── portfolio_regime_YYYYMMDD_HHMMSS.html  # Interactive HTML report
```

The HTML report automatically opens in your default browser after generation.

## Requirements

### Required Dependencies
- pandas
- numpy
- datetime
- json
- logging

### Optional Dependencies
- **zerodha_handler**: Required for Zerodha API integration
- **plotly**: Required for charts in HTML reports
- **webbrowser**: For auto-opening HTML reports

## Configuration

### Zerodha API Setup
Ensure your Zerodha credentials are configured in your config file:
```python
# config.py or config.ini
api_key = "your_api_key"
api_secret = "your_api_secret"
```

### Fallback Behavior
If Zerodha API is not available or fails:
1. Falls back to reading positions from `data/trading_state.json`
2. If no state file exists, uses example portfolio for demonstration

## Error Handling

The script includes robust error handling:
- Gracefully handles missing Zerodha modules
- Falls back to local state files when API fails
- Continues analysis even if some ticker data is missing
- Provides clear error messages in the output

## Example Output

### Console Output
```
Loaded 118 positions from Zerodha API
====================================
PORTFOLIO REGIME ANALYSIS - 2025-06-15 12:51
====================================

PORTFOLIO SUMMARY:
Total Positions: 118
Total Value: ₹18,835,120.66
Total P&L: ₹-1,769,111.07 (-9.39%)
...
```

### HTML Report Features
- Interactive portfolio summary with metrics
- Color-coded P&L indicators
- Sortable position table
- Action priority highlighting
- Market regime insights
- Risk management recommendations

## Daily Workflow Integration

For daily portfolio monitoring, combine with the daily check script:
```bash
# Morning routine
./ML-Framework/daily_portfolio_check.sh --use-zerodha
```

This provides a complete view of your portfolio aligned with current market regimes, helping you make informed decisions about position management and risk control.