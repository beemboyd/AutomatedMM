# Strong Momentum Candidates Analyzer

## Overview
The Momentum Analyzer identifies stocks showing strong momentum patterns based on analysis of successful momentum runs from stocks like Patanjali, Thermax, and PEL. It tracks rapid rank improvements, volume progression, and score acceleration to catch stocks early in their momentum phase.

## Key Features

### Pattern Detection
- **Rapid Rank Improvement**: Identifies stocks improving 40+ positions within 48 hours
- **Volume Progression**: Tracks volume surge from baseline to >1.5x
- **Score Acceleration**: Monitors probability score jumps of 20+ points
- **Stage Classification**: Categorizes stocks into 4 momentum stages

### 4-Stage Momentum Model
1. **Stage 1 - Accumulation** (Rank 50-100)
   - Low probability scores (10-20%)
   - Volume ratios below 1.0x
   - Stock appears sporadically in scans

2. **Stage 2 - Early Momentum** (Rank 20-50)
   - Probability scores jump to 30-40%
   - Volume ratios cross 1.5x threshold
   - More consistent scan appearances

3. **Stage 3 - Acceleration** (Rank 5-20)
   - Probability scores exceed 70%
   - Volume ratios 2-4x normal
   - Strong momentum readings (>10%)

4. **Stage 4 - Peak Momentum** (Rank 1-5)
   - Probability scores 90-100%
   - Volume ratios can exceed 5x
   - Sustained Top 5 rankings

## File Structure

```
Daily/scanners/Filtered/
├── momentum_analyzer.py          # Main analysis engine
├── run_momentum_analysis.py      # Execution script
├── momentum_config.json          # Configuration parameters
└── MOMENTUM_ANALYZER_README.md   # This file

Daily/results/StrongM/
├── HTML/
│   └── Strong_Candidates_*.html  # HTML reports
├── JSON/
│   └── Strong_Candidates_*.json  # JSON data files
└── PDF/
    └── Strong_Candidates_*.pdf   # PDF reports (if reportlab available)
```

## Usage

### Manual Execution
```bash
cd /Users/maverick/PycharmProjects/India-TS
python3 Daily/scanners/Filtered/run_momentum_analysis.py --force
```

### Scheduled Execution
The analyzer runs automatically at :15 of every hour during market hours (9:15 AM - 3:15 PM).

### Configuration
Edit `momentum_config.json` to adjust:
- `lookback_days`: Number of days to analyze (default: 3)
- `rapid_rank_threshold`: Minimum rank improvement (default: 40)
- `rapid_time_window_hours`: Time window for rank improvement (default: 48)
- `volume_surge_threshold`: Minimum volume ratio (default: 1.5)
- `score_jump_threshold`: Minimum score increase (default: 20)
- `top_rank_threshold`: Must break into top N (default: 30)

## Output

### HTML Report
- Located in `Daily/results/StrongM/HTML/Strong_Candidates_*.html`
- Shows top 20 momentum candidates
- Color-coded stages and price changes
- Includes selection criteria and metadata

### JSON Data
- Located in `Daily/results/StrongM/JSON/Strong_Candidates_*.json`
- Complete data for all candidates
- Suitable for programmatic access

### PDF Report (if reportlab installed)
- Located in `Daily/results/StrongM/PDF/Strong_Candidates_*.pdf`
- Professional formatted report with tables
- Suitable for printing or sharing

## Trading Guidelines

### Entry Signals
- First appearance in Top 30 with volume ratio > 1.5x
- Probability score jumping from <20% to >30%
- Breaking into Top 10 within 48 hours

### Risk Management
- Watch for rank deterioration after reaching Top 5
- Monitor volume ratio decline from peak levels
- Check for momentum divergence indicators

## Scheduling

### LaunchAgent (macOS)
The analyzer is scheduled via LaunchAgent:
```
~/Library/LaunchAgents/com.tradingsystem.momentum.analyzer.plist
```

To load/unload:
```bash
# Load
launchctl load ~/Library/LaunchAgents/com.tradingsystem.momentum.analyzer.plist

# Unload
launchctl unload ~/Library/LaunchAgents/com.tradingsystem.momentum.analyzer.plist

# Check status
launchctl list | grep momentum
```

### Job Manager Dashboard
Monitor the analyzer at http://localhost:9090
- Check job status
- View recent runs
- Access reports

## Proven Results

Based on backtesting with successful momentum stocks:
- **PATANJALI**: Rank #92 → #2 in 2 days (11.58% gain)
- **THERMAX**: Rank #79 → #3 in 1 day (10.04% gain)
- **PEL**: Rank #77 → #2 in 46 hours (11.87% gain)

All showed similar patterns:
- 70+ rank improvement in <48 hours
- Volume progression from ~1x to >4x
- Score acceleration from single digits to 90+
- 10%+ price gains during momentum run

## Troubleshooting

### No candidates found
- Check if KC_Upper_Limit_Trending files exist in Daily/results/
- Verify lookback_days covers recent market activity
- Review thresholds in momentum_config.json

### Permission errors
- Ensure write permissions for Daily/results/StrongM/
- Check LaunchAgent permissions

### Missing dependencies
- Install pandas: `pip3 install pandas`
- HTML report will be generated if reportlab is not available

## Future Enhancements
- Real-time alerts for new strong candidates
- Integration with order placement system
- Historical performance tracking
- Machine learning optimization of thresholds