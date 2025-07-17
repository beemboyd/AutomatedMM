# G Pattern Master Trading System Guide

## 📍 Master Output Location
The master recommendations can be found at:
```
/Users/maverick/PycharmProjects/India-TS/Daily/G_Pattern_Master/
├── G_Pattern_Master_List.xlsx    # Main recommendations file
├── G_Pattern_Summary.txt         # Quick summary
├── G_Pattern_History.json        # Pattern tracking history
└── Archive/                      # Historical data
```

## 📊 Master List Contents

The **G_Pattern_Master_List.xlsx** contains:
- **Ticker**: Stock symbol
- **Sector**: Industry sector
- **Current_Pattern**: Latest pattern type
- **Current_Score**: Today's probability score (0-100)
- **Days_Tracked**: How many days in the pattern
- **First_Seen**: When pattern started
- **Max_Score**: Highest score achieved
- **H2_Days**: H2 patterns in last week
- **Volume_Surges**: Volume surge days
- **Recommendation**: ACTION TO TAKE
- **Current_Price**: Entry price
- **Stop_Loss**: Risk management level
- **Target1**: First profit target
- **Risk_Reward**: R:R ratio

## 🎯 Recommendation Categories

1. **"G PATTERN CONFIRMED - FULL POSITION (100%)"**
   - Action: Complete your position immediately
   - Criteria: 3+ H2s with volume surge
   - Risk: Use full allocation

2. **"G PATTERN DEVELOPING - DOUBLE POSITION (50%)"**
   - Action: Double your initial position
   - Criteria: 2+ H2s, building momentum
   - Risk: Scale to 50% allocation

3. **"G PATTERN DEVELOPING - INITIAL POSITION (25%)"**
   - Action: Take initial position
   - Criteria: First H2 confirmed, score 50+
   - Risk: Start with 25% allocation

4. **"PATTERN EMERGING - INITIAL POSITION (25%)"**
   - Action: Small initial position
   - Criteria: Early H2 or KC breakout
   - Risk: Exploratory 25% position

5. **"WATCH CLOSELY - PRE-ENTRY"**
   - Action: Add to watchlist, no position yet
   - Criteria: Score 40-50, pattern forming
   - Risk: None, observation only

6. **"HOLD AND MONITOR - PATTERN MATURE"**
   - Action: Hold existing position
   - Criteria: Already positioned, pattern complete
   - Risk: Maintain stops at KC middle

7. **"WATCH ONLY"**
   - Action: Monitor only
   - Criteria: Early stage or low score
   - Risk: None

## 📅 Weekly Workflow

### Monday
- Fresh scan to identify new setups
- Clear previous week's tracking
- Review: G_Pattern_Summary.txt

### Tuesday-Wednesday  
- Check for "INITIAL POSITION" recommendations
- Enter 25% positions on confirmed patterns
- Monitor "WATCH CLOSELY" stocks

### Thursday-Friday
- Look for "DOUBLE POSITION" signals
- Scale positions to 50% on volume surges
- Check for "FULL POSITION" confirmations

### Saturday
- Weekly review of all positions
- Archive the week's data
- Plan for next week

### Sunday
- System maintenance
- Review performance

## 🚀 Setup Instructions

1. **Load the plist for automated scanning:**
```bash
launchctl load ~/Library/LaunchAgents/com.india-ts.kc_g_pattern_scanner.plist
```

2. **Run manual scan anytime:**
```bash
cd /Users/maverick/PycharmProjects/India-TS/Daily
python scanners/KC_Upper_Limit_Trending.py
python scanners/G_Pattern_Master_Tracker.py
```

3. **Check master recommendations:**
```bash
open G_Pattern_Master/G_Pattern_Master_List.xlsx
```

4. **Run weekly workflow:**
```bash
./utils/weekly_g_pattern_workflow.sh
```

## 📈 Position Management

### Entry Rules:
- Never enter below score 50
- Always start with 25% position
- Double only on volume confirmation
- Full position only on G Pattern confirmed

### Exit Rules:
- Stop Loss: KC Middle or 2 ATR
- Target 1: 2x risk (50% exit)
- Target 2: 3x risk (full exit)
- Time Stop: Exit if no progress in 10 days

### Risk Management:
- Maximum 3 positions in G Patterns
- Never risk more than 2% per trade
- Scale out on targets, not in

## 🔍 Quick Commands

View today's summary:
```bash
cat /Users/maverick/PycharmProjects/India-TS/Daily/G_Pattern_Master/G_Pattern_Summary.txt
```

Check specific ticker history:
```bash
python -c "import json; h=json.load(open('G_Pattern_Master/G_Pattern_History.json')); print(h.get('TICKER', 'Not found'))"
```

## 📊 Success Metrics

Track your success with:
- Win Rate: Target 60%+ on G Patterns
- Risk/Reward: Maintain 1:2 minimum
- Holding Period: 5-15 days average
- Position Building: 3-5 days to full size

---

Remember: The key to success is patience. Wait for G Patterns to develop fully before committing significant capital.