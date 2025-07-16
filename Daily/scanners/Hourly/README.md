# VSR Momentum Scanner

## Overview
The VSR (Volume Spread Ratio) Momentum Scanner identifies stocks with strong momentum using hourly data analysis. It combines volume analysis with price spread to detect momentum surges early.

## What is VSR?
- **VSR = Volume × Price Spread**
- Higher VSR values indicate strong momentum with volume support
- VSR Ratio compares current VSR to its moving average
- Multiple VSR surges indicate sustained momentum building

## Key Features
1. **Hourly Timeframe**: Captures intraday momentum shifts early
2. **VSR Analysis**: Combines volume and price spread for momentum detection
3. **Pattern Recognition**: Identifies various momentum patterns
4. **Multi-factor Scoring**: Uses base, VSR, momentum, and advanced scores
5. **Sector Classification**: Groups results by sector for analysis

## Pattern Types
- **VSR_Extreme_Breakout**: Extreme VSR with price breakout (highest momentum)
- **VSR_Momentum_Build**: VSR surge with building momentum (position entry)
- **VSR_Pre_Breakout**: Multiple VSR surges near breakout (watch closely)
- **VSR_Trend_Aligned**: VSR activity in aligned trend (momentum starting)
- **VSR_Divergence**: Positive VSR divergence (accumulation detected)
- **VSR_Signal**: VSR expansion detected (early momentum)

## Output Files
- **Excel**: `VSR_{Date}_{Time}.xlsx` in the Hourly folder
- **HTML**: Interactive report in Detailed_Analysis/Hourly folder
- **Columns**: Ticker, Sector, Pattern, VSR metrics, scores, trading levels

## Usage
```bash
# Basic usage (default user: Sai)
python VSR_Momentum_Scanner.py

# Specify different user
python VSR_Momentum_Scanner.py -u UserName
```

## Scoring System
- **Base Score**: Fundamental momentum conditions (trend, volume, price strength)
- **VSR Score**: VSR-specific conditions (surges, expansion, momentum)
- **Momentum Score**: Price momentum and breakout conditions
- **Advanced Score**: Complex patterns and divergences
- **Probability Score**: Weighted combination of all scores (0-100)

## Trading Insights
1. **VSR Ratio > 2.0**: Significant momentum surge
2. **VSR Ratio > 3.0**: Extreme momentum, often precedes major moves
3. **Multiple Surges**: Look for 2+ VSR surges in 10 hours
4. **Entry**: When VSR surge aligns with price breakout
5. **Risk Management**: Use ATR-based stops (typically 2x ATR)

## Requirements
- Zerodha Kite API credentials in config.ini
- Python packages: pandas, numpy, kiteconnect
- Optional: reportlab for PDF generation

## Schedule Recommendation
Run hourly during market hours (9:15 AM to 3:30 PM) to catch momentum shifts early.