# Price-Volume Analysis Module

This module provides tools for analyzing price and volume patterns in stocks to identify accumulation and distribution phases.

## Concepts

### Accumulation vs Distribution

This module implements analysis based on the following price-volume relationships:

1. **Accumulation Patterns:**
   - Price increases with a volume spike (smart money buying)
   - Price decreases with low volume (lack of selling pressure)

2. **Distribution Patterns:**
   - Price decreases with a volume spike (smart money selling)
   - Price increases with low volume (lack of buying conviction)

### Key Metrics

- **Volume Spike:** Volume significantly higher than recent average
- **Low Volume:** Volume significantly lower than recent average
- **Phase Strength:** Combines the signal direction with the volume ratio
- **Cumulative Phase Strength:** Running total of phase strength over time

## Usage

### Basic Analysis

```python
from ML.PV.accumulation_distribution_analyzer import analyze_ticker

# Analyze a ticker with default settings (5 days of data)
results = analyze_ticker("RELIANCE")

# Analyze with custom settings
results = analyze_ticker("HDFCBANK", days=10, output_dir="/path/to/output")
```

### Running Analysis for Multiple Tickers

```python
from ML.PV.example_analysis import run_analysis_for_tickers

# Analyze a list of tickers
tickers = ["RELIANCE", "HDFCBANK", "TCS", "INFY"]
results = run_analysis_for_tickers(tickers, days=5)
```

### Command Line Usage

```bash
# Analyze a single ticker
python -m ML.PV.accumulation_distribution_analyzer --ticker RELIANCE --days 5

# Analyze multiple tickers
python -m ML.PV.example_analysis --tickers RELIANCE HDFCBANK TCS --days 5
```

## Interpretation

### Current Phase
The most recent identified phase (accumulation, distribution, or neutral).

### Dominant Phase
The phase that appears most frequently in the recent data.

### Recent Trend
Overall direction based on the net phase strength.

### Trading Implications

- **Accumulation:** Suggests institutional buying interest and potential upward price movement
- **Distribution:** Suggests institutional selling pressure and potential downward price movement
- **Neutral:** No clear institutional bias detected; price may continue sideways

## Requirements

- Python 3.6+
- pandas
- numpy
- matplotlib

## Example Output

The analyzer generates:

1. A detailed analysis report 
2. Visual charts showing price, volume, and phase strength
3. Summary statistics for phase identification

## Notes

This analyzer works best with 5-minute intraday data but can be adapted for other timeframes.